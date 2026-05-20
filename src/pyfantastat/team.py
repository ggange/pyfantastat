"""Team class for managing fantasy team data."""


class Team:
    """Represents a fantasy team with points and statistics."""

    def __init__(self, team_name: str, user_name: str):
        """
        :param team_name: Name of the fantasy team.
        :param user_name: Name of the team owner.
        """
        self.team_name = team_name
        self.user_name = user_name
        self.fanta_pts_scored: list[float] = []
        self.fanta_pts_against: list[float] = []
        self.color: str = ""
        self.goals_scored: int = 0
        self.goals_conceded: int = 0
        self.id: int | None = None

    def add_fanta_pts_scored(self, pts: list[float]) -> None:
        """Extend the list of fantasy points scored each matchday."""
        self.fanta_pts_scored.extend(pts)

    def add_fanta_pts_against(self, pts: list[float]) -> None:
        """Extend the list of fantasy points conceded each matchday."""
        self.fanta_pts_against.extend(pts)

    def add_color(self, color: str) -> None:
        """Set the team color used for plotting."""
        self.color = color

    def add_goals(self, scored: int, conceded: int) -> None:
        """Accumulate goals scored and conceded (called each matchday)."""
        self.goals_scored += scored
        self.goals_conceded += conceded

    def _set_id(self, team_id: int) -> None:
        """Assign a unique integer ID (called by Championship.__init__)."""
        self.id = team_id
