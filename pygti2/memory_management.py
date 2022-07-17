import logging
import sys
from typing import List, Tuple

from pygti2.device_proxy import LibProxy, VarProxy

logger = logging.getLogger(__name__)


class SimpleMemoryManager:
    def __init__(self, lib: LibProxy, name_of_heap: str = "gti2_memory"):
        self.lib = lib
        var = getattr(lib, name_of_heap)
        self.base_addr = var.address
        self.max_size = lib.sizeof(var)
        self.allocated: List[Tuple[VarProxy, int]] = []

    def malloc(self, variable: VarProxy):
        self.autofree()

        required_size = self.lib.sizeof(variable)
        address = self._find_slot(required_size)
        logger.debug(
            f"SimpleMemoryManager:malloc: {required_size} @ {address:08x} (={address - self.base_addr})"
        )

        variable.address = address
        self.allocated.append((variable, required_size))

    def autofree(self):
        i = 0
        while i < len(self.allocated):
            var, size = self.allocated[i]
            count = sys.getrefcount(var)
            # Remove objects which are not referenced anymore
            if count == 3:
                logger.debug(
                    "SimpleMemoryManager:autofree: "
                    f"{size} @ {var.address:08x} (={var.address - self.base_addr})"
                )
                del self.allocated[i]
            i += 1

    def _find_slot(self, required_size: int) -> int:
        self.allocated.sort(key=lambda entry: entry[0].address)
        search_address = self.base_addr
        for var, size in self.allocated:
            if var.address - search_address >= required_size:
                return search_address
            search_address = var.address + size
        if self.base_addr + self.max_size - search_address >= required_size:
            return search_address
        raise MemoryError("Out of memory.")
