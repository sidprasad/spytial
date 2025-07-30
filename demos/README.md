# sPyTial Demos: The Documentation

**The demos ARE the documentation.** Each demo is a pedagogical journey that teaches core sPyTial concepts through working examples.

## 🎯 Why Demos as Documentation?

Traditional documentation tells you WHAT tools do. These demos teach you HOW to think spatially about your data and WHY spatial visualization transforms programming.

**Each demo reveals something fundamental:**
- **Demo 1**: How spatial constraints compose through inheritance
- **Demo 2**: How annotations work on individual objects without modifying classes  
- **Demo 3**: How custom providers transform library internals into domain insight

---

## 📚 The Three Core Demos

### 🌳 [Demo 1: Data Structures](01-simple-data-structures.ipynb)
**Trees → Red-Black Trees → Unsatisfiable Structures**

Learn how spatial constraints define structure, how annotations compose through inheritance, and how sPyTial acts as a spatial type checker.

**Key Insight**: Trees aren't just linked data—they have spatial meaning that sPyTial makes explicit and verifiable.

### 🎯 [Demo 2: Object Annotations](02-object-annotations.ipynb) 
**Individual Objects, Custom Views**

See how to annotate specific objects (like sets) without modifying their classes. The ergonomic API lets you apply spatial constraints to individual instances.

**Key Insight**: You can customize how ANY object appears spatially without touching its class definition.

### ⚡ [Demo 3: Z3 Providers](03-z3-case-study.ipynb)
**From Default Chaos to Structured Insight**

Transform Z3's internal visualization into domain-specific spatial layouts through custom providers. See the "notational relational view" you actually want.

**Key Insight**: Libraries give you power but terrible default visualizations. Providers bridge the semantic gap.

---

## 📖 Learning Path

**For Understanding Core Concepts:**
1. [Demo 1: Data Structures](01-simple-data-structures.ipynb) - Spatial constraints and inheritance
2. [Demo 2: Object Annotations](02-object-annotations.ipynb) - Instance-level customization
3. [Demo 3: Z3 Providers](03-z3-case-study.ipynb) - Domain-specific visualization

**For Quick Overview:**
- Start with [Demo Showcase](00-demo-showcase.ipynb) to see all capabilities

**For Specific Use Cases:**
- **Data Science**: [Pandas Integration](04-pandas-integration.ipynb)
- **Advanced Structures**: [Enhanced Data Structures](05-enhanced-data-structures.ipynb)
- **Extension Development**: [Provider Development](06-provider-development.ipynb)

---

## 🎓 Pedagogical Design

Each demo follows a **reveal pattern**:

### Demo 1: Trees → RBTrees → Unsatisfiable Trees
Shows how spatial constraints compose and act as structural type checkers.

### Demo 2: Default Sets → Annotated Sets → Mixed Annotations  
Shows how object-level annotations work without class modification.

### Demo 3: Default Z3 → Custom Provider → Complex Domain
Shows how providers transform internal representations into domain insight.

This isn't just "here are features"—it's "here's how to think spatially."

---

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

---

## 🌟 Key Concepts Demonstrated

### Spatial Programming
The demos show that sPyTial isn't just visualization—it's **spatial programming** where structure and meaning are unified:

- **Spatial constraints** define what valid structure looks like
- **Inheritance composition** builds complex spatial rules from simple ones  
- **Object-level annotations** customize individual instances
- **Custom providers** bridge semantic gaps between libraries and domains
- **Spatial verification** catches structural bugs through constraint violations

### Visual Debugging
- **Constraint violations** through spatial feedback
- **Data structure integrity** checking  
- **Semantic translation** from internal to domain representations

### Integration Patterns
- **Augmenting** existing tools rather than replacing them
- **Complementary** visualization approaches
- **Domain-specific** spatial reasoning through providers

---

## 🚀 Beyond The Demos

Once you understand the patterns from these three demos, you can:

- **Apply spatial constraints** to your own data structures
- **Write custom providers** for domain-specific libraries  
- **Use object annotations** for one-off visualization needs
- **Combine techniques** for complex spatial programming

The demos teach **transferable patterns**, not just tool usage.

---

## 💡 Tips for Exploration

**Run the notebooks interactively** - sPyTial's spatial visualizations are best experienced in Jupyter

**Follow the pedagogical order** - Each demo builds on concepts from previous ones

**Experiment with your own data** - Try the patterns on your domain objects

**Focus on patterns, not features** - The goal is learning spatial thinking

---

## 🤝 Contributing

Found a great use case for sPyTial? Consider contributing a demo notebook:

1. Follow the pedagogical pattern: Problem → Insight → Pattern
2. Show clear advantages of spatial thinking
3. Include traditional vs sPyTial comparisons  
4. Focus on transferable patterns
5. Add to this README

---

## 📚 Further Reading

- [Main sPyTial README](../README.md) - Core concepts and installation
- [Object Annotations Guide](../OBJECT_ANNOTATIONS.md) - Advanced annotation techniques  
- [Agents Documentation](../agents.md) - Extension possibilities

---

**The Big Idea**: These demos ARE documentation because they teach you to think spatially about your domain. Once you see structure as spatial relationships, you can't go back to pure text debugging.

**Happy spatial programming! 🌟**