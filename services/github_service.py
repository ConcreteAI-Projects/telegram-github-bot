import base64
from typing import Optional
from github import Github
from github.GithubException import GithubException

from config import GITHUB_TOKEN, GITHUB_REPO


class GitHubService:
    """Service for interacting with GitHub API."""

    # Business Impact label colors (GitHub label hex colors)
    IMPACT_COLORS = {
        "high": "d73a4a",    # Red
        "mid": "fbca04",     # Yellow
        "low": "0e8a16",     # Green
    }

    # Urgency label colors
    URGENCY_COLORS = {
        "asap": "b60205",    # Dark red
        "soon": "d93f0b",    # Orange
        "future": "0e8a16",  # Green
    }

    # Type label colors
    TYPE_COLORS = {
        "feature-new": "a2eeef",   # Light blue
        "feature-improved": "7057ff",  # Purple
        "task": "0075ca",          # Blue
    }

    # Status label colors
    STATUS_COLORS = {
        "raw-idea": "f9d0c4",      # Light pink
        "need-design": "fef2c0",   # Light yellow
        "todo": "c2e0c6",          # Light green
    }

    def __init__(self):
        self.github = Github(GITHUB_TOKEN)
        self.repo = self.github.get_repo(GITHUB_REPO)
        self._ensure_labels_exist()

    def _ensure_labels_exist(self):
        """Create impact, urgency, type, and status labels if they don't exist."""
        existing_labels = {label.name for label in self.repo.get_labels()}

        labels_to_create = [
            # Business Impact labels
            ("impact: high", self.IMPACT_COLORS["high"], "High business impact"),
            ("impact: mid", self.IMPACT_COLORS["mid"], "Medium business impact"),
            ("impact: low", self.IMPACT_COLORS["low"], "Low business impact"),
            # Urgency labels
            ("urgency: asap", self.URGENCY_COLORS["asap"], "Needed ASAP"),
            ("urgency: soon", self.URGENCY_COLORS["soon"], "Needed soon"),
            ("urgency: future", self.URGENCY_COLORS["future"], "Future enhancement"),
            # Type labels
            ("type: feature-new", self.TYPE_COLORS["feature-new"], "New feature"),
            ("type: feature-improved", self.TYPE_COLORS["feature-improved"], "Improved feature"),
            ("type: task", self.TYPE_COLORS["task"], "Task"),
            # Status labels
            ("status: raw-idea", self.STATUS_COLORS["raw-idea"], "Raw idea - needs refinement"),
            ("status: need-design", self.STATUS_COLORS["need-design"], "Needs design work"),
            ("status: todo", self.STATUS_COLORS["todo"], "Ready to work on"),
        ]

        for name, color, description in labels_to_create:
            if name not in existing_labels:
                try:
                    self.repo.create_label(name=name, color=color, description=description)
                except GithubException:
                    pass  # Label might already exist or no permission

    def create_issue(
        self,
        title: str,
        body: str,
        impact: str,
        urgency: str,
        issue_type: str = "feature-new",
        status: str = "todo",
        image_data: Optional[bytes] = None,
    ) -> dict:
        """
        Create a new GitHub issue.

        Args:
            title: Issue title
            body: Issue description/body
            impact: Business impact level (high, mid, low)
            urgency: Urgency level (asap, soon, future)
            issue_type: Type of issue (bug, feature-new, feature-improved, task)
            status: Issue status (raw-idea, need-design, todo)
            image_data: Optional screenshot bytes

        Returns:
            dict with issue number and URL
        """
        # Build labels
        labels = [
            f"impact: {impact}",
            f"urgency: {urgency}",
            f"type: {issue_type}",
            f"status: {status}",
        ]

        # Handle image upload if provided
        if image_data:
            image_url = self._upload_image(image_data, title)
            if image_url:
                body += f"\n\n### Screenshot\n![Screenshot]({image_url})"

        # Create the issue
        issue = self.repo.create_issue(
            title=title,
            body=body,
            labels=labels,
        )

        return {
            "number": issue.number,
            "url": issue.html_url,
            "title": issue.title,
        }

    def _upload_image(self, image_data: bytes, title: str) -> Optional[str]:
        """
        Upload image to the repository and return the URL.

        Creates images in a .github/issue-images/ directory.
        """
        import hashlib
        from datetime import datetime

        # Generate unique filename
        hash_suffix = hashlib.md5(image_data).hexdigest()[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f".github/issue-images/{timestamp}_{hash_suffix}.png"

        try:
            # Check if file exists
            try:
                self.repo.get_contents(filename)
                # File exists, add extra suffix
                filename = f".github/issue-images/{timestamp}_{hash_suffix}_2.png"
            except GithubException:
                pass  # File doesn't exist, good to create

            # Create/update file
            self.repo.create_file(
                path=filename,
                message=f"Add screenshot for: {title[:50]}",
                content=image_data,
            )

            # Return raw URL for the image
            return f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{filename}"

        except GithubException as e:
            print(f"Failed to upload image: {e}")
            return None

    def edit_issue(
        self,
        issue_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        impact: Optional[str] = None,
        urgency: Optional[str] = None,
        state: Optional[str] = None,
    ) -> dict:
        """
        Edit an existing GitHub issue.

        Args:
            issue_number: The issue number to edit
            title: New title (optional)
            body: New body (optional)
            impact: New business impact level (optional)
            urgency: New urgency level (optional)
            state: New state - 'open' or 'closed' (optional)

        Returns:
            dict with updated issue info
        """
        issue = self.repo.get_issue(issue_number)

        # Update basic fields
        update_kwargs = {}
        if title:
            update_kwargs["title"] = title
        if body:
            update_kwargs["body"] = body
        if state:
            update_kwargs["state"] = state

        if update_kwargs:
            issue.edit(**update_kwargs)

        # Update labels if impact or urgency provided
        if impact or urgency:
            current_labels = [label.name for label in issue.labels]
            new_labels = current_labels.copy()

            if impact:
                # Remove old impact labels
                new_labels = [l for l in new_labels if not l.startswith("impact:")]
                new_labels.append(f"impact: {impact}")

            if urgency:
                # Remove old urgency labels
                new_labels = [l for l in new_labels if not l.startswith("urgency:")]
                new_labels.append(f"urgency: {urgency}")

            issue.set_labels(*new_labels)

        return {
            "number": issue.number,
            "url": issue.html_url,
            "title": issue.title,
            "state": issue.state,
        }

    def list_issues(self, state: str = "open", limit: int = 10) -> list:
        """
        List recent issues.

        Args:
            state: Issue state ('open', 'closed', 'all')
            limit: Maximum number of issues to return

        Returns:
            List of issue dicts
        """
        issues = self.repo.get_issues(state=state, sort="updated", direction="desc")

        result = []
        for i, issue in enumerate(issues):
            if i >= limit:
                break
            # Get impact and urgency from labels
            impact = "unknown"
            urgency = "unknown"
            for label in issue.labels:
                if label.name.startswith("impact:"):
                    impact = label.name.replace("impact: ", "")
                elif label.name.startswith("urgency:"):
                    urgency = label.name.replace("urgency: ", "")

            result.append({
                "number": issue.number,
                "title": issue.title,
                "impact": impact,
                "urgency": urgency,
                "state": issue.state,
                "url": issue.html_url,
            })

        return result


# Lazy-loaded global instance
_github_service = None


def get_github_service() -> GitHubService:
    """Get or create the GitHub service instance (lazy initialization)."""
    global _github_service
    if _github_service is None:
        _github_service = GitHubService()
    return _github_service


# For backwards compatibility - will be initialized on first access
class _LazyGitHubService:
    """Lazy proxy for GitHubService."""

    def __getattr__(self, name):
        return getattr(get_github_service(), name)


github_service = _LazyGitHubService()
