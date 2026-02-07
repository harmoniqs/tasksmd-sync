"""GitHub Projects v2 GraphQL client."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date

import httpx

logger = logging.getLogger(__name__)

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"


@dataclass
class ProjectField:
    """A custom field on a GitHub Project board."""

    id: str
    name: str
    data_type: str  # e.g. "SINGLE_SELECT", "TEXT", "DATE", "ASSIGNEES"
    options: dict[str, str] = field(default_factory=dict)  # name -> option_id


@dataclass
class ProjectItem:
    """An item on the GitHub Project board."""

    item_id: str  # ProjectV2Item ID (PVTI_...)
    content_id: str | None = None  # The underlying Issue/DraftIssue/PR node ID
    content_type: str | None = None  # "Issue", "DraftIssue", "PullRequest"
    title: str = ""
    status: str = ""
    assignee: str | None = None
    labels: list[str] = field(default_factory=list)
    due_date: date | None = None
    description: str = ""


class GitHubProjectClient:
    """Client for interacting with GitHub Projects v2 via GraphQL."""

    def __init__(self, token: str, org: str, project_number: int) -> None:
        self.token = token
        self.org = org
        self.project_number = project_number
        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self._project_id: str | None = None
        self._fields: dict[str, ProjectField] | None = None

    def _graphql(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query and return the response data."""
        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables
        resp = self._client.post(GITHUB_GRAPHQL_URL, json=payload)
        resp.raise_for_status()
        body = resp.json()
        if "errors" in body:
            raise RuntimeError(f"GraphQL errors: {json.dumps(body['errors'], indent=2)}")
        return body.get("data", {})

    # ------------------------------------------------------------------
    # Project discovery
    # ------------------------------------------------------------------

    def get_project_id(self) -> str:
        """Fetch the node ID for the project."""
        if self._project_id:
            return self._project_id
        query = """
        query($org: String!, $number: Int!) {
          organization(login: $org) {
            projectV2(number: $number) {
              id
            }
          }
        }
        """
        data = self._graphql(query, {"org": self.org, "number": self.project_number})
        self._project_id = data["organization"]["projectV2"]["id"]
        return self._project_id

    def get_fields(self) -> dict[str, ProjectField]:
        """Fetch all custom fields for the project. Returns {name: ProjectField}."""
        if self._fields is not None:
            return self._fields

        project_id = self.get_project_id()
        query = """
        query($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              fields(first: 50) {
                nodes {
                  ... on ProjectV2Field {
                    id
                    name
                    dataType
                  }
                  ... on ProjectV2SingleSelectField {
                    id
                    name
                    dataType
                    options {
                      id
                      name
                    }
                  }
                  ... on ProjectV2IterationField {
                    id
                    name
                    dataType
                  }
                }
              }
            }
          }
        }
        """
        data = self._graphql(query, {"projectId": project_id})
        nodes = data["node"]["fields"]["nodes"]
        fields: dict[str, ProjectField] = {}
        for node in nodes:
            if not node.get("name"):
                continue
            options = {}
            if "options" in node:
                options = {opt["name"]: opt["id"] for opt in node["options"]}
            fields[node["name"]] = ProjectField(
                id=node["id"],
                name=node["name"],
                data_type=node.get("dataType", ""),
                options=options,
            )
        self._fields = fields
        return fields

    # ------------------------------------------------------------------
    # Read items
    # ------------------------------------------------------------------

    def list_items(self) -> list[ProjectItem]:
        """List all items on the project board (paginated)."""
        project_id = self.get_project_id()
        fields = self.get_fields()
        status_field = fields.get("Status")

        items: list[ProjectItem] = []
        cursor: str | None = None
        has_next = True

        while has_next:
            query = """
            query($projectId: ID!, $cursor: String) {
              node(id: $projectId) {
                ... on ProjectV2 {
                  items(first: 100, after: $cursor) {
                    pageInfo { hasNextPage endCursor }
                    nodes {
                      id
                      fieldValues(first: 20) {
                        nodes {
                          ... on ProjectV2ItemFieldTextValue {
                            field { ... on ProjectV2Field { name } }
                            text
                          }
                          ... on ProjectV2ItemFieldDateValue {
                            field { ... on ProjectV2Field { name } }
                            date
                          }
                          ... on ProjectV2ItemFieldSingleSelectValue {
                            field { ... on ProjectV2SingleSelectField { name } }
                            name
                          }
                          ... on ProjectV2ItemFieldUserValue {
                            field { ... on ProjectV2Field { name } }
                            users(first: 1) {
                              nodes { login }
                            }
                          }
                          ... on ProjectV2ItemFieldLabelValue {
                            field { ... on ProjectV2Field { name } }
                            labels(first: 20) {
                              nodes { name }
                            }
                          }
                        }
                      }
                      content {
                        ... on Issue {
                          title
                          body
                          assignees(first: 5) {
                            nodes { login }
                          }
                          labels(first: 20) {
                            nodes { name }
                          }
                        }
                        ... on DraftIssue {
                          title
                          body
                          assignees(first: 5) {
                            nodes { login }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
            """
            variables: dict = {"projectId": project_id, "cursor": cursor}
            data = self._graphql(query, variables)
            page = data["node"]["items"]
            has_next = page["pageInfo"]["hasNextPage"]
            cursor = page["pageInfo"]["endCursor"]

            for node in page["nodes"]:
                item = self._parse_item_node(node, status_field)
                items.append(item)

        return items

    def _parse_item_node(
        self, node: dict, status_field: ProjectField | None
    ) -> ProjectItem:
        item = ProjectItem(item_id=node["id"])
        content = node.get("content") or {}

        item.title = content.get("title", "")
        item.description = content.get("body", "") or ""

        # Assignees from content
        assignee_nodes = (content.get("assignees") or {}).get("nodes") or []
        if assignee_nodes:
            item.assignee = assignee_nodes[0].get("login")

        # Labels from content
        label_nodes = (content.get("labels") or {}).get("nodes") or []
        item.labels = [ln["name"] for ln in label_nodes if ln.get("name")]

        # Field values
        for fv in (node.get("fieldValues") or {}).get("nodes") or []:
            if not fv:
                continue
            field_info = fv.get("field") or {}
            fname = field_info.get("name", "")

            if fname == "Status" and "name" in fv:
                item.status = fv["name"]
            elif fname == "Due" and "date" in fv:
                try:
                    item.due_date = date.fromisoformat(fv["date"])
                except (ValueError, TypeError):
                    pass

        return item

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def add_draft_issue(self, title: str, body: str = "") -> str:
        """Add a draft issue to the project. Returns the new item ID."""
        project_id = self.get_project_id()
        mutation = """
        mutation($projectId: ID!, $title: String!, $body: String) {
          addProjectV2DraftIssue(input: {
            projectId: $projectId,
            title: $title,
            body: $body
          }) {
            projectItem { id }
          }
        }
        """
        data = self._graphql(
            mutation,
            {"projectId": project_id, "title": title, "body": body},
        )
        return data["addProjectV2DraftIssue"]["projectItem"]["id"]

    def update_item_field_text(self, item_id: str, field_id: str, value: str) -> None:
        """Update a text field on a project item."""
        project_id = self.get_project_id()
        mutation = """
        mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: String!) {
          updateProjectV2ItemFieldValue(input: {
            projectId: $projectId,
            itemId: $itemId,
            fieldId: $fieldId,
            value: { text: $value }
          }) {
            projectV2Item { id }
          }
        }
        """
        self._graphql(
            mutation,
            {
                "projectId": project_id,
                "itemId": item_id,
                "fieldId": field_id,
                "value": value,
            },
        )

    def update_item_field_single_select(
        self, item_id: str, field_id: str, option_id: str
    ) -> None:
        """Update a single-select field on a project item."""
        project_id = self.get_project_id()
        mutation = """
        mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
          updateProjectV2ItemFieldValue(input: {
            projectId: $projectId,
            itemId: $itemId,
            fieldId: $fieldId,
            value: { singleSelectOptionId: $optionId }
          }) {
            projectV2Item { id }
          }
        }
        """
        self._graphql(
            mutation,
            {
                "projectId": project_id,
                "itemId": item_id,
                "fieldId": field_id,
                "optionId": option_id,
            },
        )

    def update_item_field_date(self, item_id: str, field_id: str, value: date) -> None:
        """Update a date field on a project item."""
        project_id = self.get_project_id()
        mutation = """
        mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: Date!) {
          updateProjectV2ItemFieldValue(input: {
            projectId: $projectId,
            itemId: $itemId,
            fieldId: $fieldId,
            value: { date: $value }
          }) {
            projectV2Item { id }
          }
        }
        """
        self._graphql(
            mutation,
            {
                "projectId": project_id,
                "itemId": item_id,
                "fieldId": field_id,
                "value": value.isoformat(),
            },
        )

    def update_draft_issue_body(self, item_id: str, title: str, body: str) -> None:
        """Update a draft issue's title and body.

        Note: Draft issues don't have a separate content node mutation in the
        Projects v2 API. We use the updateProjectV2DraftIssue mutation.
        """
        mutation = """
        mutation($itemId: ID!, $title: String!, $body: String) {
          updateProjectV2DraftIssue(input: {
            draftIssueId: $itemId,
            title: $title,
            body: $body
          }) {
            draftIssue { id }
          }
        }
        """
        self._graphql(mutation, {"itemId": item_id, "title": title, "body": body})

    def archive_item(self, item_id: str) -> None:
        """Archive an item from the project board."""
        project_id = self.get_project_id()
        mutation = """
        mutation($projectId: ID!, $itemId: ID!) {
          archiveProjectV2Item(input: {
            projectId: $projectId,
            itemId: $itemId
          }) {
            item { id }
          }
        }
        """
        self._graphql(
            mutation, {"projectId": project_id, "itemId": item_id}
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
