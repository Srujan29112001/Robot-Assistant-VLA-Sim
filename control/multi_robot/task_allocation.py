"""Task Allocation Algorithms for Multi-Robot Systems"""
import numpy as np
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class TaskAllocator:
    """Optimal task allocation using auction-based methods"""

    def allocate_auction(self, robots: List, tasks: List) -> Dict:
        """Auction-based task allocation"""
        allocation = {}
        for i, task in enumerate(tasks):
            bids = [(r.robot_id, r.battery_level) for r in robots if all(c in r.capabilities for c in task.required_capabilities)]
            if bids:
                winner = max(bids, key=lambda x: x[1])
                allocation[task.task_id] = winner[0]
        return allocation
