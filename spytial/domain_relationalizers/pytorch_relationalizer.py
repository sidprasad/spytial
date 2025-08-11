"""Relationalizer for PyTorch tensors and neural network modules."""

from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation

try:
    import torch
    import torch.nn as nn

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    nn = None


class PyTorchTensorRelationalizer(RelationalizerBase):
    """Handles PyTorch tensor objects."""

    def can_handle(self, obj: Any) -> bool:
        if not TORCH_AVAILABLE:
            return False
        return isinstance(obj, torch.Tensor)

    def relationalize(self, obj: Any, walker_func) -> Tuple[Atom, List[Relation]]:
        obj_id = walker_func._get_id(obj)

        # Create tensor description
        shape_str = "x".join(str(s) for s in obj.shape)
        dtype_str = str(obj.dtype).replace("torch.", "")
        device_str = str(obj.device)

        label = f"Tensor[{shape_str}] {dtype_str}"
        if device_str != "cpu":
            label += f" on {device_str}"

        atom = Atom(id=obj_id, type="PyTorchTensor", label=label)

        relations = []

        # For small tensors, we can show some values
        if obj.numel() <= 10 and obj.numel() > 0:
            try:
                if obj.dim() == 0:  # scalar
                    value = obj.item()
                    vid = walker_func(value)
                    relations.append(
                        Relation(name="value", source_id=obj_id, target_id=vid)
                    )
                elif obj.dim() == 1 and obj.numel() <= 5:  # small vector
                    for i, value in enumerate(obj.tolist()):
                        vid = walker_func(value)
                        relations.append(
                            Relation(name=f"[{i}]", source_id=obj_id, target_id=vid)
                        )
            except Exception:
                # If we can't access values (e.g., on GPU without CUDA), skip
                pass

        return atom, relations


class PyTorchModuleRelationalizer(RelationalizerBase):
    """Handles PyTorch neural network modules."""

    def can_handle(self, obj: Any) -> bool:
        if not TORCH_AVAILABLE:
            return False
        return isinstance(obj, nn.Module)

    def relationalize(self, obj: Any, walker_func) -> Tuple[Atom, List[Relation]]:
        obj_id = walker_func._get_id(obj)
        module_name = type(obj).__name__

        # Count parameters
        try:
            param_count = sum(p.numel() for p in obj.parameters())
            label = f"{module_name} ({param_count:,} params)"
        except Exception:
            label = module_name

        atom = Atom(id=obj_id, type="PyTorchModule", label=label)

        relations = []

        # Add child modules
        for name, child_module in obj.named_children():
            vid = walker_func(child_module)
            relations.append(Relation(name=name, source_id=obj_id, target_id=vid))

        # Add parameters (only for leaf modules to avoid clutter)
        if len(list(obj.children())) == 0:  # leaf module
            for name, param in obj.named_parameters(recurse=False):
                if param is not None:
                    vid = walker_func(param)
                    relations.append(
                        Relation(name=name, source_id=obj_id, target_id=vid)
                    )

        return atom, relations
