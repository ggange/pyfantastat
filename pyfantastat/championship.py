"""Championship class for managing league calculations and rankings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import numpy as np

from pyfantastat.team import Team

if TYPE_CHECKING:
    from pyfantastat.io.models import CalendarData


class Championship:
    """Manages championship calculations, rankings, and analytics."""

    def __init__(
        self,
        teams: list[Team],
        competition_type: str = "Standard",
        goal_threshold: int | None = None,
        interval: bool = False,
        only_in_range: bool = False,
        pt_interval: float | None = None,
        card_order: list[str] | None = None,
    ):
        """
        :param teams: Team objects participating in the championship.
        :param competition_type: ``"Standard"`` (``"Mantra"`` not yet supported).
        :param goal_threshold: Point gap between consecutive goal thresholds.
            Defaults to 5 (thresholds at 66, 71, 76, 81, 86, 91, 96).
        :param interval: If True, award/deny a goal based on point-difference bands.
        :param only_in_range: When ``interval=True``, apply the band rule only to
            tied matches (not all matches).
        :param pt_interval: Minimum point difference required to trigger the band
            goal when ``interval=True``.
        :param card_order: Ordered list of tiebreaker criteria. Supported values:
            ``"Punti"``, ``"Somma punti totale"``, ``"Classifica avulsa"``,
            ``"Differenza reti"``, ``"Gol fatti"``, ``"Gol subiti"``.
        """
        if competition_type == "Standard":
            self.competition_type = "Standard"
        elif competition_type == "Mantra":
            raise NotImplementedError("Mantra competition type is not yet implemented.")
        else:
            raise ValueError(
                "Invalid competition type. Allowed values are 'Standard' and 'Mantra'."
            )

        self.teams = teams
        for team_id, team in enumerate(self.teams):
            team._set_id(team_id)

        self.ranking: np.ndarray = np.zeros(len(self.teams))
        self.goal_threshold = goal_threshold
        self.interval = interval
        self.pt_interval = pt_interval
        self.only_in_range = only_in_range
        self.card_order: list[str] = card_order if card_order is not None else []
        self.calendar: list[list[list[int]]] | None = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_calendar_data(cls, data: "CalendarData", **kwargs) -> "Championship":
        """Construct a Championship directly from a :class:`CalendarData` object.

        Example::

            ch = Championship.from_calendar_data(load_calendar_xlsx("league.xlsx"))
            ch.generate_ranking()

        All keyword arguments are forwarded to ``__init__`` (e.g. ``card_order``,
        ``goal_threshold``, ``interval``).
        """
        teams = []
        for name, username in zip(data.team_names, data.user_names):
            t = Team(name, username)
            t.add_fanta_pts_scored(data.team_points[name])
            teams.append(t)
        ch = cls(teams, **kwargs)
        ch.set_calendar(data.calendar)
        ch.set_current_matchday(data.current_matchday)
        return ch

    # ------------------------------------------------------------------
    # Calendar
    # ------------------------------------------------------------------

    def set_calendar(self, calendar: list[list[list[int]]]) -> None:
        """Set the match calendar.

        :param calendar: A list of matchdays; each matchday is a list of matches;
            each match is ``[team_idx_home, team_idx_away]``.
        :raises ValueError: If any matchday does not contain exactly
            ``len(teams) // 2`` matches.
        """
        for rnd in calendar:
            if len(rnd) != len(self.teams) // 2:
                raise ValueError(
                    "Each matchday must contain exactly half the number of teams."
                )
        self.calendar = calendar

    def set_current_matchday(self, matchday: int) -> None:
        """Set the current matchday index (0-based).

        :param matchday: Index of the last completed matchday.
        :raises ValueError: If calendar is not set or matchday is out of range.
        """
        if self.calendar is None:
            raise ValueError("Calendar must be set before setting current matchday.")
        if matchday < 0 or matchday >= len(self.calendar):
            raise ValueError(f"Matchday index {matchday} is out of range.")
        self.current_matchday = matchday

    # ------------------------------------------------------------------
    # Match result helpers
    # ------------------------------------------------------------------

    def _goal_limits(self) -> np.ndarray:
        """Return the array of point thresholds used to count goals."""
        if self.goal_threshold is not None:
            return np.arange(66, 66 + self.goal_threshold * 8, self.goal_threshold)
        return np.arange(66, 101, 5)  # default: 66, 71, 76, 81, 86, 91, 96

    def match_result(
        self, match: list[int], matchday: int
    ) -> tuple[int, np.ndarray]:
        """Determine the outcome of a single match.

        :param match: ``[team_idx_a, team_idx_b]``
        :param matchday: Zero-based matchday index.
        :returns: ``(result, goals)`` where ``result`` is 1 (team A wins),
            2 (team B wins), or 0 (draw), and ``goals`` is an array of
            ``[goals_a, goals_b]``.
        """
        limits = self._goal_limits()
        goals = np.zeros(2)

        for k, m in enumerate(match):
            pts = self.teams[m].fanta_pts_scored[matchday]
            for h, lim in enumerate(limits, start=1):
                if pts >= lim:
                    goals[k] = h
                else:
                    break

        if self.interval and self.pt_interval is not None:
            pts_a = self.teams[match[0]].fanta_pts_scored[matchday]
            pts_b = self.teams[match[1]].fanta_pts_scored[matchday]
            self._apply_interval(goals, pts_a, pts_b)

        return self._goals_to_result(goals), goals

    def match_result_from_points(
        self, pts_a: float, pts_b: float
    ) -> tuple[int, np.ndarray]:
        """Determine match outcome directly from two fantapoint values.

        Useful for what-if calculations without needing team objects.

        :param pts_a: Fantapoints of team A.
        :param pts_b: Fantapoints of team B.
        :returns: ``(result, goals)`` — same convention as :meth:`match_result`.
        """
        limits = self._goal_limits()
        goals = np.zeros(2)

        for k, pts in enumerate([pts_a, pts_b]):
            for h, lim in enumerate(limits, start=1):
                if pts >= lim:
                    goals[k] = h
                else:
                    break

        if self.interval and self.pt_interval is not None:
            self._apply_interval(goals, pts_a, pts_b)

        return self._goals_to_result(goals), goals

    def _apply_interval(
        self, goals: np.ndarray, pts_a: float, pts_b: float
    ) -> None:
        """Mutate ``goals`` in-place according to the interval (band) rule."""
        diff = pts_a - pts_b
        if self.only_in_range:
            # Band rule only when teams are already tied on goals
            if goals[0] == goals[1]:
                if diff >= self.pt_interval and pts_a >= 66:
                    goals[0] += 1
                elif -diff >= self.pt_interval and pts_b >= 66:
                    goals[1] += 1
        else:
            if diff >= self.pt_interval and pts_a >= 66:
                goals[0] += 1
            elif -diff >= self.pt_interval and pts_b >= 66:
                goals[1] += 1
            else:
                g_min = np.min(goals)
                goals[:] = g_min

    @staticmethod
    def _goals_to_result(goals: np.ndarray) -> int:
        if goals[0] > goals[1]:
            return 1
        if goals[0] < goals[1]:
            return 2
        return 0

    # ------------------------------------------------------------------
    # Ranking generation
    # ------------------------------------------------------------------

    def generate_ranking(self) -> None:
        """Compute league points for all teams from the current calendar.

        Also accumulates :attr:`~pyfantastat.team.Team.goals_scored` and
        :attr:`~pyfantastat.team.Team.goals_conceded` on each team.

        :raises ValueError: If :meth:`set_calendar` has not been called.
        """
        if not self.calendar:
            raise ValueError("Calendar must be set before generating ranking.")

        # Reset so the method is idempotent
        self.ranking = np.zeros(len(self.teams))
        for t in self.teams:
            t.goals_scored = 0
            t.goals_conceded = 0

        for day_idx, day in enumerate(self.calendar[:self.current_matchday if self.current_matchday is not None else None]):
            for match in day:
                res, goals = self.match_result(match, day_idx)
                if res == 1:
                    self.ranking[match[0]] += 3
                elif res == 2:
                    self.ranking[match[1]] += 3
                else:
                    self.ranking[match[0]] += 1
                    self.ranking[match[1]] += 1
                self.teams[match[0]].add_goals(goals[0], goals[1])
                self.teams[match[1]].add_goals(goals[1], goals[0])

    # ------------------------------------------------------------------
    # Ranking sorting / tiebreakers
    # ------------------------------------------------------------------

    def sort_ranking(self) -> tuple[np.ndarray, Optional[str]]:
        """Sort teams by ranking with configured tiebreakers.

        :returns: ``(sorted_indices, warning_message)`` where
            ``sorted_indices[0]`` is the index of the first-place team.
            ``warning_message`` is set when three or more teams are tied.
        """
        values, counts = np.unique(self.ranking, return_counts=True)
        arg_sort = np.argsort(-self.ranking, kind="stable")
        warning_message: Optional[str] = None

        if np.any(counts > 1):
            for dup_value_id in np.where(counts > 1)[0]:
                tied_value = values[dup_value_id]
                orig_ids = np.flatnonzero(self.ranking == tied_value)

                if len(orig_ids) > 2:
                    warning_message = (
                        "Potrebbero esserci più di due squadre appaiate in classifica. "
                        "Ci stiamo lavorando!"
                    )

                pos_in_sort = np.flatnonzero(np.isin(arg_sort, orig_ids))

                for card in self.card_order:
                    if card == "Punti":
                        continue

                    elif card == "Somma punti totale":
                        totals = np.array(
                            [np.sum(self.teams[i].fanta_pts_scored) for i in orig_ids]
                        )
                        if np.unique(totals).size == 1:
                            continue
                        order = np.argsort(-totals, kind="stable")
                        arg_sort[pos_in_sort] = arg_sort[pos_in_sort][order]
                        break

                    elif card == "Classifica avulsa":
                        mini_pts = np.zeros(len(orig_ids))
                        for day_idx, day in enumerate(self.calendar):
                            for match in day:
                                if match[0] in orig_ids and match[1] in orig_ids:
                                    res, _ = self.match_result(match, day_idx)
                                    pos0 = list(orig_ids).index(match[0])
                                    pos1 = list(orig_ids).index(match[1])
                                    if res == 1:
                                        mini_pts[pos0] += 3
                                    elif res == 2:
                                        mini_pts[pos1] += 3
                                    else:
                                        mini_pts[pos0] += 1
                                        mini_pts[pos1] += 1
                        if np.unique(mini_pts).size == 1:
                            continue
                        order = np.argsort(-mini_pts, kind="stable")
                        arg_sort[pos_in_sort] = arg_sort[pos_in_sort][order]
                        break

                    elif card == "Differenza reti":
                        diff = np.array(
                            [
                                self.teams[i].goals_scored - self.teams[i].goals_conceded
                                for i in orig_ids
                            ]
                        )
                        if np.unique(diff).size == 1:
                            continue
                        order = np.argsort(-diff, kind="stable")
                        arg_sort[pos_in_sort] = arg_sort[pos_in_sort][order]
                        break

                    elif card == "Gol fatti":
                        scored = np.array(
                            [self.teams[i].goals_scored for i in orig_ids]
                        )
                        if np.unique(scored).size == 1:
                            continue
                        order = np.argsort(-scored, kind="stable")
                        arg_sort[pos_in_sort] = arg_sort[pos_in_sort][order]
                        break

                    elif card == "Gol subiti":
                        conceded = np.array(
                            [self.teams[i].goals_conceded for i in orig_ids]
                        )
                        if np.unique(conceded).size == 1:
                            continue
                        # Fewer goals conceded is better → ascending sort
                        order = np.argsort(conceded, kind="stable")
                        arg_sort[pos_in_sort] = arg_sort[pos_in_sort][order]
                        break

        return arg_sort, warning_message

    def team_position(self, team_id: int) -> int:
        """Return the 1-based league position of the team with the given ID.

        :param team_id: The :attr:`~pyfantastat.team.Team.id` of the team.
        """
        sorted_indices, _ = self.sort_ranking()
        for pos, idx in enumerate(sorted_indices, start=1):
            if idx == team_id:
                return pos
        raise ValueError(f"Team with id {team_id} not found in ranking.")

    def match_for_team(self, team_id: int, matchday: int) -> list[int]:
        """Return the match pair ``[idx_a, idx_b]`` for a team on a given matchday.

        :param team_id: The :attr:`~pyfantastat.team.Team.id` of the team.
        :param matchday: Zero-based matchday index.
        :raises ValueError: If calendar is not set or matchday is out of range.
        """
        if self.calendar is None:
            raise ValueError("Calendar must be set before checking matches.")
        if matchday >= len(self.calendar):
            raise ValueError(f"Matchday {matchday} is out of range.")
        for match in self.calendar[matchday]:
            if self.teams[match[0]].id == team_id or self.teams[match[1]].id == team_id:
                return match
        raise ValueError(f"Team {team_id} not found in matchday {matchday}.")

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def get_wins_draws_losses(self) -> dict[str, dict[str, int]]:
        """Return win/draw/loss counts per team.

        :returns: ``{"Team A": {"W": 3, "D": 1, "L": 2}, ...}``
        :raises ValueError: If calendar is not set.
        """
        if self.calendar is None:
            raise ValueError("Calendar must be set before computing statistics.")

        result: dict[str, dict[str, int]] = {
            t.team_name: {"W": 0, "D": 0, "L": 0} for t in self.teams
        }
        for day_idx, day in enumerate(self.calendar[: self.current_matchday if self.current_matchday is not None else None]):
            for match in day:
                res, _ = self.match_result(match, day_idx)
                name_a = self.teams[match[0]].team_name
                name_b = self.teams[match[1]].team_name
                if res == 1:
                    result[name_a]["W"] += 1
                    result[name_b]["L"] += 1
                elif res == 2:
                    result[name_b]["W"] += 1
                    result[name_a]["L"] += 1
                else:
                    result[name_a]["D"] += 1
                    result[name_b]["D"] += 1
        return result

    def strength_of_schedule(self, team_idx: int) -> float:
        """Return the average fantapoints of all opponents a team has faced.

        :param team_idx: Index into :attr:`teams`.
        :raises ValueError: If calendar is not set.
        """
        if self.calendar is None:
            raise ValueError("Calendar must be set before computing statistics.")

        opponent_scores: list[float] = []
        for day_idx, day in enumerate(self.calendar):
            for match in day:
                if match[0] == team_idx:
                    opponent_scores.append(self.teams[match[1]].fanta_pts_scored[day_idx])
                elif match[1] == team_idx:
                    opponent_scores.append(self.teams[match[0]].fanta_pts_scored[day_idx])
        if not opponent_scores:
            return 0.0
        return float(np.mean(opponent_scores))

    def total_fpt_ranking(self) -> list[tuple[str, float]]:
        """Rank teams by total (sum) of fantapoints scored, descending.

        :returns: List of ``(team_name, total_pts)`` sorted best-first.
        """
        totals = [(t.team_name, float(np.sum(t.fanta_pts_scored))) for t in self.teams]
        return sorted(totals, key=lambda x: x[1], reverse=True)

    def lowest_scoring_day(self) -> tuple[int, float]:
        """Return the matchday with the lowest combined fantapoints across all matches.

        :returns: ``(matchday_index, combined_score)``
        :raises ValueError: If calendar is not set.
        """
        if self.calendar is None:
            raise ValueError("Calendar must be set before computing statistics.")

        day_scores = []
        for day_idx, day in enumerate(self.calendar):
            total = sum(
                self.teams[match[0]].fanta_pts_scored[day_idx]
                + self.teams[match[1]].fanta_pts_scored[day_idx]
                for match in day
            )
            day_scores.append((day_idx, total))
        return min(day_scores, key=lambda x: x[1])

    def highest_scoring_day(self) -> tuple[int, float]:
        """Return the matchday with the highest combined fantapoints across all matches.

        :returns: ``(matchday_index, combined_score)``
        :raises ValueError: If calendar is not set.
        """
        if self.calendar is None:
            raise ValueError("Calendar must be set before computing statistics.")

        day_scores = []
        for day_idx, day in enumerate(self.calendar):
            total = sum(
                self.teams[match[0]].fanta_pts_scored[day_idx]
                + self.teams[match[1]].fanta_pts_scored[day_idx]
                for match in day
            )
            day_scores.append((day_idx, total))
        return max(day_scores, key=lambda x: x[1])

    def number_close_matches(self) -> dict[str, int]:
        """Count matches where ``|pts_diff| ≤ 3`` and both teams scored ≥ 66.

        :returns: ``{"Team A": 2, ...}`` — count per team.
        :raises ValueError: If calendar is not set.
        """
        if self.calendar is None:
            raise ValueError("Calendar must be set before computing statistics.")

        counts: dict[str, int] = {t.team_name: 0 for t in self.teams}
        for day_idx, day in enumerate(self.calendar):
            for match in day:
                pts_a = self.teams[match[0]].fanta_pts_scored[day_idx]
                pts_b = self.teams[match[1]].fanta_pts_scored[day_idx]
                if pts_a >= 66 and pts_b >= 66 and abs(pts_a - pts_b) <= 3:
                    counts[self.teams[match[0]].team_name] += 1
                    counts[self.teams[match[1]].team_name] += 1
        return counts

    def close_draws(self) -> dict[str, int]:
        """Count draws where ``|pts_diff| ≤ 3`` and both teams scored ≥ 66.

        :returns: ``{"Team A": 1, ...}`` — count per team.
        :raises ValueError: If calendar is not set.
        """
        if self.calendar is None:
            raise ValueError("Calendar must be set before computing statistics.")

        counts: dict[str, int] = {t.team_name: 0 for t in self.teams}
        for day_idx, day in enumerate(self.calendar):
            for match in day:
                pts_a = self.teams[match[0]].fanta_pts_scored[day_idx]
                pts_b = self.teams[match[1]].fanta_pts_scored[day_idx]
                res, _ = self.match_result(match, day_idx)
                if res == 0 and pts_a >= 66 and pts_b >= 66 and abs(pts_a - pts_b) <= 3:
                    counts[self.teams[match[0]].team_name] += 1
                    counts[self.teams[match[1]].team_name] += 1
        return counts

    def what_if_calendar(
        self, team_a_idx: int, team_b_idx: int
    ) -> tuple[int, int]:
        """Simulate what team A's league points would be if it had played team B's opponents.

        :param team_a_idx: Index of team A (the team whose points we recalculate).
        :param team_b_idx: Index of team B (the team whose schedule we borrow).
        :returns: ``(actual_points_a, what_if_points_a)``
        :raises ValueError: If calendar is not set.
        """
        if self.calendar is None:
            raise ValueError("Calendar must be set before computing statistics.")

        actual_pts = int(self.ranking[team_a_idx])
        what_if_pts = 0

        for day_idx, day in enumerate(self.calendar):
            # Find team B's opponent on this day
            opponent_b_idx: int | None = None
            for match in day:
                if match[0] == team_b_idx:
                    opponent_b_idx = match[1]
                    break
                if match[1] == team_b_idx:
                    opponent_b_idx = match[0]
                    break
            if opponent_b_idx is None:
                continue

            pts_a = self.teams[team_a_idx].fanta_pts_scored[day_idx]
            pts_opp = self.teams[opponent_b_idx].fanta_pts_scored[day_idx]
            res, _ = self.match_result_from_points(pts_a, pts_opp)
            if res == 1:
                what_if_pts += 3
            elif res == 0:
                what_if_pts += 1

        return actual_pts, what_if_pts

    def prizes(self) -> dict:
        """Return the highest and lowest individual scoring performances.

        :returns: Dictionary with keys ``"highest"`` and ``"lowest"``, each
            containing ``{"team_name": str, "matchday": int, "points": float}``.
        """
        best: dict | None = None
        worst: dict | None = None

        for day_idx, day in enumerate(self.calendar or []):
            for match in day:
                for team_idx in match:
                    pts = self.teams[team_idx].fanta_pts_scored[day_idx]
                    entry = {
                        "team_name": self.teams[team_idx].team_name,
                        "matchday": day_idx,
                        "points": pts,
                    }
                    if best is None or pts > best["points"]:
                        best = entry
                    if worst is None or pts < worst["points"]:
                        worst = entry

        return {"highest": best, "lowest": worst}
