from typing import cast, Optional

from sebs.cache import Cache
from sebs.faas.config import Config, Credentials, Resources
from sebs.storage.resources import SelfHostedResources
from sebs.storage.config import NoSQLStorageConfig, PersistentStorageConfig
from sebs.utils import LoggingHandlers


class CloudburstCredentials(Credentials):
    def serialize(self) -> dict:
        return {}

    @staticmethod
    def deserialize(config: dict, cache: Cache, handlers: LoggingHandlers) -> Credentials:
        return CloudburstCredentials()


class CloudburstResources(SelfHostedResources):
    def __init__(
        self,
        storage_cfg: Optional[PersistentStorageConfig] = None,
        nosql_storage_cfg: Optional[NoSQLStorageConfig] = None,
    ):
        super().__init__("cloudburst", storage_cfg, nosql_storage_cfg)

    def serialize(self) -> dict:
        return super().serialize()

    @staticmethod
    def initialize(res: Resources, config: dict):
        pass

    def update_cache(self, cache: Cache):
        super().update_cache(cache)

    @staticmethod
    def deserialize(config: dict, cache: Cache, handlers: LoggingHandlers) -> Resources:
        ret = CloudburstResources()
        ret._resources_id = "cloudburst-predeployed"
        ret.logging_handlers = handlers
        return ret


class CloudburstConfig(Config):
    def __init__(
        self,
        scheduler_ip: str = "",
        client_ip: str = "",
        local: bool = True,
        cloudburst_path: str = "",
    ):
        super().__init__(name="cloudburst")
        self._credentials = CloudburstCredentials()
        self._resources = CloudburstResources()
        self._scheduler_ip = scheduler_ip
        self._client_ip = client_ip
        self._local = local
        self._cloudburst_path = cloudburst_path

    @staticmethod
    def typename() -> str:
        return "Cloudburst.Config"

    @staticmethod
    def initialize(cfg: Config, dct: dict):
        pass

    @property
    def credentials(self) -> CloudburstCredentials:
        return self._credentials

    @property
    def resources(self) -> CloudburstResources:
        return self._resources

    @resources.setter
    def resources(self, val: CloudburstResources):
        self._resources = val

    @property
    def scheduler_ip(self) -> str:
        return self._scheduler_ip

    @property
    def client_ip(self) -> str:
        return self._client_ip

    @property
    def local(self) -> bool:
        return self._local

    @property
    def cloudburst_path(self) -> str:
        return self._cloudburst_path

    @staticmethod
    def deserialize(config: dict, cache: Cache, handlers: LoggingHandlers) -> Config:
        config_obj = CloudburstConfig(
            scheduler_ip=config.get("scheduler_ip", ""),
            client_ip=config.get("client_ip", ""),
            local=config.get("local", True),
            cloudburst_path=config.get("cloudburst_path", ""),
        )
        config_obj.logging_handlers = handlers
        return config_obj

    def serialize(self) -> dict:
        return {
            "name": "cloudburst",
            "region": self._region,
            "scheduler_ip": self._scheduler_ip,
            "client_ip": self._client_ip,
            "local": self._local,
            "cloudburst_path": self._cloudburst_path,
        }

    def update_cache(self, cache: Cache):
        self.resources.update_cache(cache)
