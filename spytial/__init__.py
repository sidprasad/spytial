from .provider_system import CnDDataInstanceBuilder, DataInstanceProvider, data_provider
from .visualizer import diagram, quick_diagram
from .provider_system import CnDDataInstanceBuilder, DataInstanceProvider, data_provider

# Aliases for the new branding
SpyTialDataInstanceBuilder = CnDDataInstanceBuilder
SpyTialSerializer = CnDDataInstanceBuilder

__all__ = ['diagram', 'quick_diagram', 'CnDDataInstanceBuilder', 'SpyTialDataInstanceBuilder', 'DataInstanceProvider', 'data_provider', 'SpyTialSerializer']

# Backwards compatibility aliases
CnDSerializer = CnDDataInstanceBuilder

__all__ = ['CnDDataInstanceBuilder', 'DataInstanceProvider', 'data_provider', 'show', 'quick_show', 'CnDSerializer']

