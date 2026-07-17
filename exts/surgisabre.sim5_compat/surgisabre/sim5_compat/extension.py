from __future__ import annotations

import sys
import types
from typing import Any

import carb
import omni.ext
import omni.physics.tensors as tensors
from omni.physics.tensors import api as tensors_api


class Sim5TensorNamespaceCompatExtension(omni.ext.IExt):
    """Expose the Sim 6 tensor API at the namespace used by pinned Isaac Lab."""

    def on_startup(self, _ext_id: str) -> None:
        impl_name = "omni.physics.tensors.impl"
        api_name = f"{impl_name}.api"

        # Isaac Sim 6 removed the old soft-body class names. The pinned Lab
        # revision evaluates these names only in annotations while importing
        # its asset modules. Keep them import-only rather than pretending the
        # replacement deformable APIs have the same runtime semantics.
        if not hasattr(tensors_api, "SoftBodyView"):
            tensors_api.SoftBodyView = Any
        if not hasattr(tensors_api, "SoftBodyMaterialView"):
            tensors_api.SoftBodyMaterialView = Any

        impl = sys.modules.get(impl_name)
        if impl is None:
            impl = types.ModuleType(impl_name)
            impl.__path__ = []
            impl.__package__ = impl_name
            sys.modules[impl_name] = impl

        impl.api = tensors_api
        sys.modules[api_name] = tensors_api
        tensors.impl = impl
        carb.log_info(
            "[surgisabre.sim5_compat] Aliased omni.physics.tensors.impl.api "
            "and import-only soft-body annotations to the Isaac Sim 6 tensor API"
        )

    def on_shutdown(self) -> None:
        # Isaac Lab modules retain references to this alias for process lifetime.
        pass
