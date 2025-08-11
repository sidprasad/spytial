"""Relationalizer for ANTLR parse trees."""

from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation

try:
    # Try to import ANTLR runtime
    from antlr4 import ParserRuleContext, TerminalNode, ErrorNode
    from antlr4.tree.Tree import ParseTree

    ANTLR_AVAILABLE = True
except ImportError:
    ANTLR_AVAILABLE = False
    ParserRuleContext = None
    TerminalNode = None
    ErrorNode = None
    ParseTree = None


class ANTLRParseTreeRelationalizer(RelationalizerBase):
    """Handles ANTLR parse tree nodes."""

    def can_handle(self, obj: Any) -> bool:
        if not ANTLR_AVAILABLE:
            return False
        return isinstance(obj, (ParserRuleContext, TerminalNode, ErrorNode))

    def relationalize(self, obj: Any, walker_func) -> Tuple[Atom, List[Relation]]:
        obj_id = walker_func._get_id(obj)

        if isinstance(obj, TerminalNode):
            # Terminal node - leaf of the parse tree
            symbol_text = str(obj.getSymbol().text) if obj.getSymbol() else "<?>"
            atom = Atom(id=obj_id, type="ANTLRTerminal", label=f'"{symbol_text}"')
            relations = []

        elif isinstance(obj, ErrorNode):
            # Error node
            symbol_text = str(obj.getSymbol().text) if obj.getSymbol() else "<?>"
            atom = Atom(id=obj_id, type="ANTLRError", label=f"ERROR: {symbol_text}")
            relations = []

        elif isinstance(obj, ParserRuleContext):
            # Rule context - internal node
            rule_name = type(obj).__name__
            if rule_name.endswith("Context"):
                rule_name = rule_name[:-7]  # Remove 'Context' suffix

            # Try to get rule index for more specific naming
            try:
                rule_index = obj.getRuleIndex()
                if hasattr(obj, "parser") and obj.parser:
                    rule_names = obj.parser.ruleNames
                    if 0 <= rule_index < len(rule_names):
                        rule_name = rule_names[rule_index]
            except Exception:
                pass

            atom = Atom(id=obj_id, type="ANTLRRule", label=rule_name)

            relations = []
            # Add children
            if hasattr(obj, "getChildCount") and obj.getChildCount() > 0:
                for i in range(obj.getChildCount()):
                    child = obj.getChild(i)
                    if child is not None:
                        vid = walker_func(child)
                        relations.append(
                            Relation(name=f"child_{i}", source_id=obj_id, target_id=vid)
                        )
        else:
            # Fallback for unknown parse tree types
            atom = Atom(id=obj_id, type="ANTLRNode", label=str(type(obj).__name__))
            relations = []

        return atom, relations
