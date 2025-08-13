#!/usr/bin/env python3
"""
Demonstration of n-ary relations in sPyTial.

This example shows how to create and use n-ary relations (relations connecting
more than 2 atoms) using custom relationalizers.
"""

import spytial
from spytial import RelationalizerBase, relationalizer, Atom, Relation
from typing import Any, List, Tuple


@relationalizer(priority=100)
class CourseRelationalizer(RelationalizerBase):
    """
    Example relationalizer that creates ternary relations for courses.

    Creates a 'teaches' relation connecting: instructor -> course -> semester
    """

    def can_handle(self, obj: Any) -> bool:
        return (
            isinstance(obj, dict)
            and "instructor" in obj
            and "course" in obj
            and "semester" in obj
        )

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        # Create main course atom
        course_id = walker_func._get_id(obj)
        course_atom = Atom(
            id=course_id, type="course", label=f"Course: {obj['course']}"
        )

        # Create atoms for instructor and semester
        instructor_id = walker_func(obj["instructor"])
        semester_id = walker_func(obj["semester"])

        # Create ternary relation: instructor teaches course in semester
        teaches_relation = Relation.from_atoms(
            "teaches", [instructor_id, course_id, semester_id]
        )

        # Also create binary relations for comparison
        instructor_course_rel = Relation.binary("instructs", instructor_id, course_id)
        course_semester_rel = Relation.binary("offered_in", course_id, semester_id)

        return [course_atom], [
            teaches_relation,
            instructor_course_rel,
            course_semester_rel,
        ]


@relationalizer(priority=101)
class MeetingRelationalizer(RelationalizerBase):
    """
    Example relationalizer that creates quaternary relations for meetings.

    Creates a 'participates_in' relation connecting all participants with the meeting.
    """

    def can_handle(self, obj: Any) -> bool:
        return (
            isinstance(obj, dict)
            and "meeting_title" in obj
            and "participants" in obj
            and isinstance(obj["participants"], list)
        )

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        # Create main meeting atom
        meeting_id = walker_func._get_id(obj)
        meeting_atom = Atom(
            id=meeting_id, type="meeting", label=f"Meeting: {obj['meeting_title']}"
        )

        # Create atoms for all participants
        participant_ids = [
            walker_func(participant) for participant in obj["participants"]
        ]

        # Create n-ary relation connecting meeting with all participants
        if participant_ids:
            participates_relation = Relation.from_atoms(
                "participates_in",
                [meeting_id] + participant_ids,  # meeting + all participants
            )
            return [meeting_atom], [participates_relation]
        else:
            return [meeting_atom], []


def demonstrate_nary_relations():
    """Demonstrate n-ary relations with practical examples."""

    print("=== N-ary Relations Demonstration ===\n")

    # Example 1: Ternary relation (3 atoms)
    print("1. Ternary Relation Example:")
    print("   Creating 'teaches' relation: instructor -> course -> semester")

    course_data = {
        "instructor": "Dr. Smith",
        "course": "Computer Science 101",
        "semester": "Fall 2024",
    }

    result1 = spytial.diagram(course_data, method="file", auto_open=False)
    print(f"   ✓ Visualization saved to: {result1}")

    # Show the underlying data structure
    builder = spytial.CnDDataInstanceBuilder()
    data_instance = builder.build_instance(course_data)

    print("   Relations created:")
    for rel in data_instance["relations"]:
        tuple_data = rel["tuples"][0] if rel["tuples"] else {"atoms": [], "types": []}
        arity = len(tuple_data["atoms"])
        print(f"     - {rel['name']}: {arity}-ary relation")
        if rel["name"] == "teaches":
            print(f"       Connects: {' -> '.join(tuple_data['types'])}")

    print()

    # Example 2: Quaternary+ relation (4+ atoms)
    print("2. Quaternary+ Relation Example:")
    print("   Creating 'participates_in' relation: meeting + all participants")

    meeting_data = {
        "meeting_title": "Project Planning Session",
        "participants": ["Alice", "Bob", "Charlie", "Diana"],
    }

    result2 = spytial.diagram(meeting_data, method="file", auto_open=False)
    print(f"   ✓ Visualization saved to: {result2}")

    # Show the underlying data structure
    data_instance2 = builder.build_instance(meeting_data)

    print("   Relations created:")
    for rel in data_instance2["relations"]:
        tuple_data = rel["tuples"][0] if rel["tuples"] else {"atoms": [], "types": []}
        arity = len(tuple_data["atoms"])
        print(f"     - {rel['name']}: {arity}-ary relation")
        if rel["name"] == "participates_in":
            print(f"       Connects: meeting + {arity-1} participants")

    print()

    # Example 3: Direct Relation API usage
    print("3. Direct N-ary Relation API:")

    # Create relations directly
    binary_rel = Relation.binary("follows", "user1", "user2")
    ternary_rel = Relation.from_atoms("coordinates", ["x", "y", "z"])
    quaternary_rel = Relation.from_atoms(
        "transaction", ["sender", "receiver", "amount", "timestamp"]
    )

    print(f"   Binary relation: {binary_rel.arity()}-ary - {binary_rel.to_tuple()}")
    print(
        f"   Ternary relation: {ternary_rel.arity()}-ary - {ternary_rel.to_atoms_tuple()}"
    )
    print(
        f"   Quaternary relation: {quaternary_rel.arity()}-ary - {quaternary_rel.to_atoms_tuple()}"
    )

    print()

    # Example 4: Backward compatibility
    print("4. Backward Compatibility:")
    print("   Binary relations work exactly as before")

    simple_data = {"name": "John", "age": 30}
    result3 = spytial.diagram(simple_data, method="file", auto_open=False)
    print(f"   ✓ Traditional binary relations: {result3}")

    print("\n=== Summary ===")
    print("✓ N-ary relations (3+ atoms) are now supported")
    print("✓ Binary relations (2 atoms) work exactly as before")
    print("✓ Custom relationalizers can create relations of any arity")
    print("✓ Visualization system handles both binary and n-ary relations")
    print("✓ API provides convenient methods for both use cases")


if __name__ == "__main__":
    demonstrate_nary_relations()
