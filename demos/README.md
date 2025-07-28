# sPyTial Demos: Spatial Visualization for Python

This directory contains comprehensive demonstrations of sPyTial's capabilities across different domains and use cases.

## 🚀 Start Here

**New to sPyTial?** Begin with `00-demo-showcase.ipynb` for an overview of all capabilities.

## 📓 Demo Notebooks

| Notebook | Description | Best For |
|----------|-------------|----------|
| **00-demo-showcase.ipynb** | 🎯 Overview of all sPyTial capabilities | First-time users, getting oriented |
| **05-enhanced-data-structures.ipynb** | 🏗️ Core Python structures with spatial reasoning | Learning fundamentals, debugging |
| **04-pandas-integration.ipynb** | 📊 DataFrame architecture vs statistical visualization | Data science workflows |
| **03-z3-case-study.ipynb** | 🔍 Visual constraint solving and debugging | Logic programming, SMT solving |
| **02-object-annotations.ipynb** | ✨ Instance-level spatial annotations | Advanced techniques |
| **01-simple-data-structures.ipynb** | 📚 Basic usage examples | Getting started |
| **viz.ipynb** | ⚡ Quick visualization demo | Testing basic functionality |
| **z3-demo.ipynb** | ⚡ Quick Z3 example | Testing Z3 integration |

## 🎯 Use Case Guide

### When to Use sPyTial

✅ **Understanding data structure architecture**  
✅ **Debugging complex nested objects**  
✅ **Teaching/learning data structures**  
✅ **Code reviews involving data organization**  
✅ **Documenting data relationships**  
✅ **Visualizing constraint solving problems**  
✅ **Exploring DataFrame relationships**  

### When to Use Traditional Tools

📊 **Statistical analysis of data values**  
📊 **Publication-ready charts and graphs**  
📊 **Time series visualization**  
📊 **Performance monitoring dashboards**  

## 🔧 Requirements

The demos require different optional dependencies:

```bash
# Core sPyTial (always required)
pip install -r ../requirements.txt

# For pandas demos
pip install pandas numpy matplotlib seaborn

# For Z3 demos  
pip install z3-solver

# All dependencies
pip install pandas numpy matplotlib seaborn z3-solver
```

## 🌟 Key Concepts Demonstrated

### Spatial Relationships
- How sPyTial reveals **architectural patterns** invisible in text
- **Hierarchical structure** visualization
- **Connection patterns** in complex data

### Visual Debugging
- **Constraint violations** through spatial feedback
- **Data structure integrity** checking  
- **Pipeline flow** visualization

### Integration Patterns
- **Augmenting** existing tools rather than replacing them
- **Complementary** visualization approaches
- **Domain-specific** spatial reasoning

## 🎓 Learning Path

**Beginner Track:**
1. `00-demo-showcase.ipynb` - Overview
2. `01-simple-data-structures.ipynb` - Basic usage
3. `viz.ipynb` - Quick experiments

**Intermediate Track:**
1. `05-enhanced-data-structures.ipynb` - Core concepts
2. `02-object-annotations.ipynb` - Annotations
3. Your domain-specific notebook

**Advanced Track:**
1. `04-pandas-integration.ipynb` - Data science integration
2. `03-z3-case-study.ipynb` - Constraint solving
3. Create your own spatial annotations

## 💡 Tips for Exploration

**Run the notebooks interactively** - sPyTial's spatial visualizations are best experienced in Jupyter

**Experiment with your own data** - Try `diagram(your_object)` on any Python object

**Compare with traditional approaches** - Each demo shows traditional vs sPyTial side-by-side

**Focus on structure, not content** - sPyTial reveals *how* your data is organized, not *what* it contains

## 🤝 Contributing

Found a great use case for sPyTial? Consider contributing a demo notebook:

1. Follow the naming pattern: `XX-your-domain.ipynb`
2. Include traditional vs sPyTial comparisons
3. Show clear advantages of spatial visualization
4. Add to this README

## 📚 Further Reading

- [Main sPyTial README](../README.md) - Core concepts and installation
- [Object Annotations Guide](../OBJECT_ANNOTATIONS.md) - Advanced annotation techniques
- [Agents Documentation](../agents.md) - Extension possibilities

---

**Happy spatial visualization! 🌟**