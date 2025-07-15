import collections.abc
import json
import inspect
import dataclasses



class CnDSerializer:
    def __init__(self):
        self._seen = {}
        self._atoms = []
        self._rels = {}

    def serialize(self, obj):
        try:
            self._seen.clear()
            self._atoms.clear()
            self._rels.clear()
            self._walk(obj)
        except Exception as e:
            print(f"Error during serialization: {e}")
        
        # Convert relations to include types
        relations = []
        for rel_name, tuples in self._rels.items():
            # For each tuple, get the types of the atoms involved
            typed_tuples = []
            for source_id, target_id in tuples:
                source_type = self._get_atom_type(source_id)
                target_type = self._get_atom_type(target_id)
                typed_tuples.append({
                    "atoms": [source_id, target_id],
                    "types": [source_type, target_type]
                })
            
            relations.append({
                "id": rel_name,
                "name": rel_name,
                "types": ["object", "object"],  # Default to Python's top type
                "tuples": typed_tuples
            })
        
        return {
            "atoms": self._atoms,
            "relations": relations
        }

    def _walk(self, obj, depth=0, max_depth=100):
        if depth > max_depth:
            raise RecursionError("Maximum recursion depth exceeded")

        oid = id(obj)
        if oid in self._seen:
            return self._seen[oid]

        obj_id = f"n{len(self._seen)}"
        self._seen[oid] = obj_id

        typ = type(obj).__name__
        
        # Generate meaningful, concise labels
        if isinstance(obj, (int, float, str, bool)):
            label = str(obj)
        elif isinstance(obj, (list, tuple)):
            label = f"{typ}[{len(obj)}]"
        elif isinstance(obj, (set, frozenset)):
            label = f"{typ}{{{len(obj)}}}"
        elif isinstance(obj, dict):
            label = f"{typ}{{{len(obj)}}}"
        elif hasattr(obj, "__dict__") or hasattr(obj, "__slots__"):
            label = f"{typ}"
        else:
            label = f"{typ}"

        self._atoms.append({"id": obj_id, "type": typ, "label": label})

        # Handle primitive types
        if isinstance(obj, (int, float, str, bool)):
            return obj_id

        # Handle collections (list, tuple, set, frozenset)
        if isinstance(obj, (list, tuple, set, frozenset)):
            for i, elt in enumerate(obj):
                eid = self._walk(elt, depth + 1)
                if isinstance(obj, (list, tuple)):
                    # For ordered collections, use simple numeric indices
                    self._rels.setdefault(str(i), []).append([obj_id, eid])
                else:
                    # For unordered collections, use generic "contains"
                    self._rels.setdefault("contains", []).append([obj_id, eid])
            return obj_id

        # Handle dictionaries - create direct field relationships
        if isinstance(obj, dict):
            for k, v in obj.items():
                vid = self._walk(v, depth + 1)
                # Use the key as the relation name, pointing directly to the value
                key_str = str(k) if isinstance(k, (str, int, float, bool)) else f"key_{len(self._rels)}"
                self._rels.setdefault(key_str, []).append([obj_id, vid])
            return obj_id

        # Handle objects with __slots__
        if hasattr(obj, "__slots__"):
            for slot in obj.__slots__:
                if hasattr(obj, slot):
                    fid = self._walk(getattr(obj, slot), depth + 1)
                    self._rels.setdefault(slot, []).append([obj_id, fid])
            return obj_id

        # Handle dataclasses
        if dataclasses.is_dataclass(obj):
            for field in dataclasses.fields(obj):
                if not field.name.startswith('_'):  # Skip private fields
                    fval = getattr(obj, field.name)
                    fid = self._walk(fval, depth + 1)
                    self._rels.setdefault(field.name, []).append([obj_id, fid])
            return obj_id

        # Handle objects with __dict__ using introspection
        if hasattr(obj, "__dict__"):
            # Use inspect to get meaningful attributes, excluding methods and private attrs
            for attr_name, attr_value in vars(obj).items():
                if not attr_name.startswith('_') and not inspect.ismethod(attr_value):
                    fid = self._walk(attr_value, depth + 1)
                    self._rels.setdefault(attr_name, []).append([obj_id, fid])
            return obj_id

        # Handle objects with __getstate__ (pickle protocol)
        if hasattr(obj, "__getstate__"):
            try:
                state = obj.__getstate__()
                if isinstance(state, dict):
                    for key, value in state.items():
                        fid = self._walk(value, depth + 1)
                        self._rels.setdefault(str(key), []).append([obj_id, fid])
                else:
                    # Handle non-dict states
                    fid = self._walk(state, depth + 1)
                    self._rels.setdefault("state", []).append([obj_id, fid])
                return obj_id
            except Exception:
                pass  # Fall through to other handlers

        # Handle other hashable objects
        if isinstance(obj, collections.abc.Hashable):
            return obj_id

        # Fallback for unsupported types
        return obj_id

    def _get_atom_type(self, atom_id):
        """Get the type of an atom by its ID."""
        for atom in self._atoms:
            if atom["id"] == atom_id:
                return atom["type"]
        return "object"  # Default fallback
