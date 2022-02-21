"""
Common procedures and classes between the v1 and v2 formats
"""

from abc import abstractmethod, ABC
from typing import Dict


class OSBuildError(Exception, ABC):

    @property
    @abstractmethod
    def ID(self) -> int:
        pass

    @property
    @abstractmethod
    def code(self) -> str:
        pass

    @property
    @abstractmethod
    def details(self) -> Dict:
        pass

    def format(self):
        return {
            "type": "error",
            "error": {
                    "id": self.ID,
                    "code": self.code,
                    "reason": str(self),
                    "details": self.details
            }
        }
