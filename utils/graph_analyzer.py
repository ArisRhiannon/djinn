"""
GraphAnalyzer — Social graph construction and analysis for Youkai Discord bot.

Provides async methods to query the messages database and perform:
- Social graph construction (co-occurrence based)
- Community detection (neighbor similarity merging)
- Influence path tracing (BFS shortest path)
- Coordinated activity detection (timing + content similarity)
- User behavior correlation (Pearson on hourly patterns)
- Anomaly scanning (z-score detection)

All methods are async and return JSON-serializable dicts.
"""
from __future__ import annotations

import asyncio
import hashlib
import math
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import aiosqlite


class GraphAnalyzer:
    """Async graph analysis engine backed by the Youkai messages database."""

    def __init__(self, db: Any) -> None:
        """
        Args:
            db: Database instance (utils.database.Database). Must have a _db
                attribute (aiosqlite.Connection) for raw queries.
        """
        self.db = db

    @property
    def _conn(self):
        return self.db._db

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _time_bucket(ts: int, window: int = 300) -> int:
        """Bucket a Unix timestamp into window-sized bins (default 5 min)."""
        return ts // window

    @staticmethod
    def _crc32_tokenize(text: str) -> Set[int]:
        """Tokenize text and hash each token with CRC32 (matching automod fingerprint)."""
        if not text:
            return set()
        tokens = text.lower().split()
        return {hashlib.crc32(t.encode()) & 0xFFFFFFFF for t in tokens if t}

    @staticmethod
    def _jaccard(set_a: Set, set_b: Set) -> float:
        """Jaccard similarity between two sets."""
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    def _pearson(self, x: List[float], y: List[float]) -> float:
        """Pearson correlation coefficient between two equal-length lists."""
        n = len(x)
        if n == 0 or len(y) != n:
            return 0.0
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        std_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
        std_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))
        if std_x == 0 or std_y == 0:
            return 0.0
        return cov / (std_x * std_y)

    async def _fetch_messages(
        self, guild_id: int, hours: int, limit: int = 200000
    ) -> List[Dict[str, Any]]:
        """Fetch messages for a guild within a time window."""
        since = int(time.time()) - hours * 3600
        return await self.db.fetch(
            "SELECT user_id, username, channel_id, content, timestamp "
            "FROM messages WHERE guild_id = ? AND timestamp > ? "
            "ORDER BY timestamp ASC LIMIT ?",
            (guild_id, since, limit),
        )

    async def _fetch_channel_names(
        self, guild_id: int, channel_ids: Set[int]
    ) -> Dict[int, str]:
        """Resolve channel IDs to names from the messages table."""
        if not channel_ids:
            return {}
        placeholders = ",".join("?" for _ in channel_ids)
        async with self._conn.execute(
            f"SELECT DISTINCT channel_id FROM messages WHERE guild_id = ? AND channel_id IN ({placeholders})",
            (guild_id, *channel_ids),
        ) as cur:
            rows = await cur.fetchall()
        # Channel names aren't stored in messages table; return IDs as names
        return {r["channel_id"]: f"channel_{r['channel_id']}" for r in rows}

    # ── Social Graph ─────────────────────────────────────────────────────

    async def build_social_graph(
        self, guild_id: int, hours: int = 168, min_interactions: int = 3
    ) -> Dict[str, Any]:
        """
        Build a social graph from message co-occurrence.

        Two users "co-occur" if they both posted messages in the same channel
        where timestamps are within 300 seconds (5 minutes) of each other.

        Returns:
            {
                "nodes": [{"id": str, "name": str, "msg_count": int}],
                "edges": [{"source": str, "target": str, "weight": int}],
                "stats": {"total_nodes": int, "total_edges": int, "density": float}
            }
        """
        messages = await self._fetch_messages(guild_id, hours)

        if not messages:
            return {"nodes": [], "edges": [], "stats": {"total_nodes": 0, "total_edges": 0, "density": 0.0}}

        # Build adjacency: (channel_id, time_bucket) -> set of user_ids
        bucket_users: Dict[Tuple[int, int], Set[int]] = defaultdict(set)
        user_msg_counts: Dict[int, int] = defaultdict(int)
        user_names: Dict[int, str] = {}

        for msg in messages:
            uid = msg["user_id"]
            cid = msg["channel_id"]
            ts = msg["timestamp"]
            bucket = self._time_bucket(ts, 300)
            key = (cid, bucket)
            bucket_users[key].add(uid)
            user_msg_counts[uid] += 1
            if uid not in user_names:
                user_names[uid] = msg.get("username", str(uid))

        # Build edge weights
        edge_weights: Dict[Tuple[str, str], int] = defaultdict(int)
        for users in bucket_users.values():
            if len(users) < 2:
                continue
            user_list = sorted(users)
            for i in range(len(user_list)):
                for j in range(i + 1, len(user_list)):
                    a, b = str(user_list[i]), str(user_list[j])
                    if a < b:
                        edge_weights[(a, b)] += 1
                    else:
                        edge_weights[(b, a)] += 1

        # Filter by min_interactions
        edges = [
            {"source": src, "target": tgt, "weight": w}
            for (src, tgt), w in edge_weights.items()
            if w >= min_interactions
        ]

        # Collect nodes that have at least one edge
        connected_users: Set[str] = set()
        for e in edges:
            connected_users.add(e["source"])
            connected_users.add(e["target"])

        nodes = [
            {
                "id": uid,
                "name": user_names.get(int(uid), uid),
                "msg_count": user_msg_counts.get(int(uid), 0),
            }
            for uid in connected_users
        ]

        n = len(nodes)
        e = len(edges)
        density = (2.0 * e) / (n * (n - 1)) if n > 1 else 0.0

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {"total_nodes": n, "total_edges": e, "density": round(density, 4)},
        }

    # ── Community Detection ──────────────────────────────────────────────

    async def find_communities(
        self, guild_id: int, min_size: int = 3, hours: int = 168
    ) -> List[Dict[str, Any]]:
        """
        Detect communities using neighbor-similarity merging.

        1. Build the social graph.
        2. Start with each user as their own community.
        3. Iteratively merge communities that share high neighbor overlap.
        4. Return communities with size >= min_size.

        Returns:
            [
                {
                    "community_id": str,
                    "members": [{"id": str, "name": str}],
                    "density": float,
                    "top_channels": [{"id": str, "name": str}]
                }
            ]
        """
        graph = await self.build_social_graph(guild_id, hours, min_interactions=1)
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        if len(nodes) < min_size:
            return []

        # Build adjacency sets
        neighbors: Dict[str, Set[str]] = defaultdict(set)
        user_names: Dict[str, str] = {}
        for n in nodes:
            user_names[n["id"]] = n["name"]
        for e in edges:
            neighbors[e["source"]].add(e["target"])
            neighbors[e["target"]].add(e["source"])

        # Initialize communities: each user is their own community
        communities: List[Set[str]] = [{uid} for uid, _ in user_names.items()]

        # Merge communities based on neighbor Jaccard similarity
        changed = True
        max_iterations = 50
        iteration = 0

        while changed and iteration < max_iterations:
            changed = False
            iteration += 1
            i = 0
            while i < len(communities):
                j = i + 1
                while j < len(communities):
                    # Compute neighbor overlap between communities
                    neighbors_i = set().union(*(neighbors.get(u, set()) for u in communities[i]))
                    neighbors_j = set().union(*(neighbors.get(u, set()) for u in communities[j]))
                    # Remove internal members
                    neighbors_i -= communities[i]
                    neighbors_j -= communities[j]

                    sim = self._jaccard(neighbors_i, neighbors_j)
                    if sim > 0.4:  # Threshold for merging
                        communities[i] |= communities[j]
                        communities.pop(j)
                        changed = True
                    else:
                        j += 1
                i += 1

        # Compute community metrics: get top channels and density for each community
        # For channel data, sample recent messages from community members
        result = []
        for idx, comm in enumerate(communities):
            if len(comm) < min_size:
                continue

            # Compute internal density: edges_within / possible_edges
            member_set = comm
            internal_edges = sum(
                1 for e in edges
                if e["source"] in member_set and e["target"] in member_set
            )
            n = len(member_set)
            possible = n * (n - 1) / 2
            density = internal_edges / possible if possible > 0 else 0.0

            # Get top channels for this community from recent messages
            member_ids = [int(uid) for uid in comm]
            placeholders = ",".join("?" for _ in member_ids)
            since = int(time.time()) - hours * 3600
            async with self._conn.execute(
                f"SELECT channel_id, COUNT(*) as cnt FROM messages "
                f"WHERE guild_id = ? AND user_id IN ({placeholders}) AND timestamp > ? "
                f"GROUP BY channel_id ORDER BY cnt DESC LIMIT 3",
                (guild_id, *member_ids, since),
            ) as cur:
                channel_rows = await cur.fetchall()

            top_channels = [
                {"id": str(r["channel_id"]), "name": f"channel_{r['channel_id']}"}
                for r in channel_rows
            ]

            members = [
                {"id": uid, "name": user_names.get(uid, uid)}
                for uid in sorted(comm)
            ]

            result.append({
                "community_id": f"c{idx + 1}",
                "members": members,
                "density": round(density, 3),
                "top_channels": top_channels,
            })

        # Sort by density descending (tightest communities first)
        result.sort(key=lambda c: c["density"], reverse=True)
        return result

    # ── Influence Path Tracing ───────────────────────────────────────────

    async def trace_influence(
        self,
        guild_id: int,
        user_a_id: str,
        user_b_id: str,
        max_depth: int = 4,
    ) -> Dict[str, Any]:
        """
        Find the shortest path between two users in the co-occurrence graph using BFS.

        Returns:
            {
                "found": bool,
                "distance": int or null,
                "path": [{"id": str, "name": str, "channel_id": str}] or null
            }
        """
        # Build graph for a reasonable window
        hours = 168  # 1 week
        graph = await self.build_social_graph(guild_id, hours, min_interactions=1)
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        user_names: Dict[str, str] = {n["id"]: n["name"] for n in nodes}

        # Build adjacency list
        adj: Dict[str, Set[str]] = defaultdict(set)
        for e in edges:
            adj[e["source"]].add(e["target"])
            adj[e["target"]].add(e["source"])

        ua = str(user_a_id)
        ub = str(user_b_id)

        # Add nodes to adjacency even if they have no edges
        for uid in (ua, ub):
            if uid not in adj:
                adj[uid] = set()

        # BFS
        from collections import deque
        visited: Dict[str, Optional[str]] = {ua: None}
        queue = deque([ua])

        while queue:
            current = queue.popleft()
            depth = 0
            # Calculate current depth by walking back
            node = current
            while visited.get(node) is not None:
                depth += 1
                node = visited[node]
                if depth > max_depth:
                    break
            if depth > max_depth:
                continue

            if current == ub:
                # Reconstruct path
                path = []
                node = ub
                while node is not None:
                    path.append({
                        "id": node,
                        "name": user_names.get(node, node),
                        "channel_id": None,  # channel info not tracked in BFS
                    })
                    node = visited[node]
                path.reverse()
                return {
                    "found": True,
                    "distance": len(path) - 1,
                    "path": path,
                }

            for neighbor in adj.get(current, set()):
                if neighbor not in visited:
                    visited[neighbor] = current
                    queue.append(neighbor)

        return {
            "found": False,
            "distance": None,
            "path": None,
        }

    # ── Coordinated Activity Detection ───────────────────────────────────

    async def detect_coordinated_activity(
        self,
        guild_id: int,
        hours: int = 24,
        similarity_threshold: float = 0.7,
        min_group_size: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Detect groups of users exhibiting coordinated activity.

        Criteria:
        1. Posted in same channels within tight time windows
        2. Have similar message content (Jaccard on CRC32 token fingerprints)

        Returns:
            [
                {
                    "user_ids": [str],
                    "names": [str],
                    "channel_id": str,
                    "similarity_score": float,
                    "message_count": int,
                    "time_window_start": int
                }
            ]
        """
        messages = await self._fetch_messages(guild_id, hours, limit=5000)

        if not messages:
            return []

        # Group messages by (channel_id, tight time bucket of 60 seconds)
        bucket_msgs: Dict[Tuple[int, int], List[Dict]] = defaultdict(list)
        for msg in messages:
            bucket = self._time_bucket(msg["timestamp"], 60)
            key = (msg["channel_id"], bucket)
            bucket_msgs[key].append(msg)

        # Within each bucket, find pairs of users with similar content
        results = []
        seen_groups: Set[Tuple[str, ...]] = set()

        for (channel_id, bucket), msgs in bucket_msgs.items():
            if len(msgs) < min_group_size:
                continue

            # Group by user within this bucket
            user_msgs: Dict[int, List[Dict]] = defaultdict(list)
            user_names: Dict[int, str] = {}
            for m in msgs:
                uid = m["user_id"]
                user_msgs[uid].append(m)
                if uid not in user_names:
                    user_names[uid] = m.get("username", str(uid))

            user_ids = list(user_msgs.keys())
            if len(user_ids) < min_group_size:
                continue

            # For each user, compute a content fingerprint (union of token CRC32s)
            fingerprints: Dict[int, Set[int]] = {}
            for uid, user_msg_list in user_msgs.items():
                fp = set()
                for m in user_msg_list:
                    fp |= self._crc32_tokenize(m.get("content", ""))
                fingerprints[uid] = fp

            # Find groups of users where all pairwise similarities exceed threshold
            # Use a simple greedy clustering approach
            groups: List[Set[int]] = []
            for uid in user_ids:
                placed = False
                for group in groups:
                    # Check if uid is similar to all members of this group
                    all_similar = all(
                        self._jaccard(fingerprints.get(uid, set()), fingerprints.get(m, set()))
                        >= similarity_threshold
                        for m in group
                    )
                    if all_similar:
                        group.add(uid)
                        placed = True
                        break
                if not placed:
                    groups.append({uid})

            for group in groups:
                if len(group) < min_group_size:
                    continue
                group_key = tuple(sorted(str(u) for u in group))
                if group_key in seen_groups:
                    continue
                seen_groups.add(group_key)

                # Compute average similarity
                sorted_users = sorted(group)
                sims = []
                for i in range(len(sorted_users)):
                    for j in range(i + 1, len(sorted_users)):
                        sims.append(
                            self._jaccard(
                                fingerprints.get(sorted_users[i], set()),
                                fingerprints.get(sorted_users[j], set()),
                            )
                        )
                avg_sim = sum(sims) / len(sims) if sims else 0.0

                total_msgs = sum(len(user_msgs.get(uid, [])) for uid in group)

                results.append({
                    "user_ids": [str(u) for u in sorted_users],
                    "names": [user_names.get(u, str(u)) for u in sorted_users],
                    "channel_id": str(channel_id),
                    "similarity_score": round(avg_sim, 3),
                    "message_count": total_msgs,
                    "time_window_start": bucket * 60,  # Convert bucket back to timestamp
                })

        # Sort by similarity score descending
        results.sort(key=lambda r: r["similarity_score"], reverse=True)
        return results

    # ── User Behavior Correlation ────────────────────────────────────────

    async def correlate_behavior(
        self,
        guild_id: int,
        user_a_id: str,
        user_b_id: str,
        hours: int = 168,
    ) -> Dict[str, Any]:
        """
        Compare activity patterns between two users.

        Computes:
        - Pearson correlation of hourly message counts
        - Shared channels with overlap counts
        - Temporal overlap percentage

        Returns:
            {
                "correlation_coefficient": float,
                "shared_channels": [{"id": str, "name": str, "overlap_count": int}],
                "temporal_overlap_pct": float,
                "verdict": "highly_correlated"|"moderately_correlated"|"uncorrelated"
            }
        """
        uid_a = int(user_a_id)
        uid_b = int(user_b_id)
        since = int(time.time()) - hours * 3600

        # Get messages for both users
        async with self._conn.execute(
            "SELECT user_id, channel_id, timestamp FROM messages "
            "WHERE guild_id = ? AND user_id IN (?, ?) AND timestamp > ? "
            "ORDER BY timestamp ASC",
            (guild_id, uid_a, uid_b, since),
        ) as cur:
            rows = await cur.fetchall()

        # Split by user
        msgs_a = [r for r in rows if r["user_id"] == uid_a]
        msgs_b = [r for r in rows if r["user_id"] == uid_b]

        # Build hourly counts
        hour_counts_a = defaultdict(int)
        hour_counts_b = defaultdict(int)

        for m in msgs_a:
            hour_bucket = m["timestamp"] // 3600
            hour_counts_a[hour_bucket] += 1

        for m in msgs_b:
            hour_bucket = m["timestamp"] // 3600
            hour_counts_b[hour_bucket] += 1

        # Align hourly vectors
        all_hours = sorted(set(hour_counts_a.keys()) | set(hour_counts_b.keys()))
        if not all_hours:
            return {
                "correlation_coefficient": 0.0,
                "shared_channels": [],
                "temporal_overlap_pct": 0.0,
                "verdict": "uncorrelated",
            }

        vec_a = [hour_counts_a.get(h, 0) for h in all_hours]
        vec_b = [hour_counts_b.get(h, 0) for h in all_hours]

        corr = self._pearson(vec_a, vec_b)

        # Shared channels
        channels_a = defaultdict(int)
        channels_b = defaultdict(int)
        for m in msgs_a:
            channels_a[m["channel_id"]] += 1
        for m in msgs_b:
            channels_b[m["channel_id"]] += 1

        shared = set(channels_a.keys()) & set(channels_b.keys())
        shared_channels = [
            {
                "id": str(cid),
                "name": f"channel_{cid}",
                "overlap_count": min(channels_a.get(cid, 0), channels_b.get(cid, 0)),
            }
            for cid in shared
        ]

        # Temporal overlap: % of hours where both were active
        hours_a = set(h for h, c in hour_counts_a.items() if c > 0)
        hours_b = set(h for h, c in hour_counts_b.items() if c > 0)
        overlap_pct = len(hours_a & hours_b) / max(len(hours_a | hours_b), 1)

        # Verdict
        if abs(corr) > 0.8:
            verdict = "highly_correlated"
        elif abs(corr) > 0.5:
            verdict = "moderately_correlated"
        else:
            verdict = "uncorrelated"

        return {
            "correlation_coefficient": round(corr, 4),
            "shared_channels": shared_channels,
            "temporal_overlap_pct": round(overlap_pct, 3),
            "verdict": verdict,
        }

    # ── Anomaly Scanning ─────────────────────────────────────────────────

    async def anomaly_scan(
        self,
        guild_id: int,
        hours: int = 168,
        sensitivity: float = 2.0,
    ) -> List[Dict[str, Any]]:
        """
        Scan server activity for anomalous message spikes per user.

        For each user:
        - Compute hourly message counts over the period
        - Calculate z-score for each hour: (count - mean) / std
        - Flag hours where z-score > sensitivity

        Returns:
            [
                {
                    "user_id": str,
                    "name": str,
                    "hour": str (ISO),
                    "z_score": float,
                    "message_count": int,
                    "expected_count": float
                }
            ]
        """
        messages = await self._fetch_messages(guild_id, hours)

        if not messages:
            return []

        # Build per-user hourly counts
        user_hours: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        user_names: Dict[int, str] = {}

        for msg in messages:
            uid = msg["user_id"]
            hour_ts = (msg["timestamp"] // 3600) * 3600  # Floor to hour
            user_hours[uid][hour_ts] += 1
            if uid not in user_names:
                user_names[uid] = msg.get("username", str(uid))

        anomalies = []

        for uid, hour_map in user_hours.items():
            counts = list(hour_map.values())
            if len(counts) < 2:  # Need at least 2 data points for z-score
                continue

            mean = sum(counts) / len(counts)
            variance = sum((c - mean) ** 2 for c in counts) / len(counts)
            std = math.sqrt(variance)
            if std == 0:
                continue  # No variation, nothing anomalous

            for hour_ts, count in sorted(hour_map.items()):
                z = (count - mean) / std
                if z > sensitivity:
                    from datetime import datetime, timezone
                    hour_str = datetime.fromtimestamp(hour_ts, tz=timezone.utc).isoformat()
                    anomalies.append({
                        "user_id": str(uid),
                        "name": user_names.get(uid, str(uid)),
                        "hour": hour_str,
                        "z_score": round(z, 2),
                        "message_count": count,
                        "expected_count": round(mean, 1),
                    })

        # Sort by z_score descending
        anomalies.sort(key=lambda a: a["z_score"], reverse=True)
        return anomalies

    # ── Interaction Heatmap ──────────────────────────────────────────────

    async def interaction_heatmap(
        self, guild_id: int, user_id: str, days: int = 7
    ) -> Dict[str, Any]:
        """
        Build a 7x24 matrix of message counts by day-of-week and hour-of-day.

        Returns:
            {
                "user_name": str,
                "data": [[count for 24h] for 7 days],
                "day_labels": ["Mon", "Tue", ...],
                "hour_labels": ["00:00", "01:00", ...]
            }
        """
        uid = int(user_id)
        since = int(time.time()) - days * 86400

        async with self._conn.execute(
            "SELECT timestamp, username FROM messages "
            "WHERE guild_id = ? AND user_id = ? AND timestamp > ? "
            "ORDER BY timestamp ASC",
            (guild_id, uid, since),
        ) as cur:
            rows = await cur.fetchall()

        from datetime import datetime, timezone

        # Initialize 7x24 matrix
        data = [[0] * 24 for _ in range(7)]
        user_name = str(uid)

        for r in rows:
            dt = datetime.fromtimestamp(r["timestamp"], tz=timezone.utc)
            day_idx = dt.weekday()  # 0=Monday, 6=Sunday
            hour_idx = dt.hour
            data[day_idx][hour_idx] += 1
            if not user_name or user_name == str(uid):
                user_name = r.get("username", str(uid))

        day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        hour_labels = [f"{h:02d}:00" for h in range(24)]

        return {
            "user_name": user_name,
            "data": data,
            "day_labels": day_labels,
            "hour_labels": hour_labels,
        }
