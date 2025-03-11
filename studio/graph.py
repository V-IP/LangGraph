import re
from pydantic import BaseModel, Field
from typing import Annotated, Dict, List
from typing_extensions import TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.constants import Send
from langgraph.graph import END, MessagesState, START, StateGraph
# from dotenv import load_dotenv
# load_dotenv()

import configuration

def extract_dorm_name(response: str, dorms: dict):
    pattern = r'\b(' + '|'.join(re.escape(dorm) for dorm in dorms.keys()) + r')\b'
    match = re.search(pattern, response)
    return match.group(1) if match else None

### LLM
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

### Schema
class Student(BaseModel):
    name: str = Field(description="Name of the student.")
    personality: str = Field(description="Personality type of the student (party person or quiet).")

class HousingState(TypedDict):
    dorms: Dict[str, Dict[str, List[str]]]
    new_student: Student
    assigned_dorm: str
    assigned_room: str

### Nodes and edges
campus_manager_instructions = """
You are the Campus Housing Manager. Your job is to assign students to dormitories based on available space.
Select the first avaible one. If no dormitories have space, return "No available dormitory."

Available Dormitories:
{dorm_list}
"""

def assign_dormitory(state: HousingState):
    dorm_list = "\n".join([
        f"{dorm}: {sum(2 - len(occupants) for occupants in rooms.values())} free spots"
        for dorm, rooms in state['dorms'].items()
    ])
    system_message = campus_manager_instructions.format(dorm_list=dorm_list)
    print("Assigning dormitory. Available dorms:\n", dorm_list)
    
    response = llm.invoke([SystemMessage(content=system_message), HumanMessage(content="Assign the student to a dormitory.")])
    try:
        result = response.content.strip()
        dorm_name = extract_dorm_name(result, state["dorms"])

        if dorm_name:
            print(f"Extracted dorm: {dorm_name}")
            return {"assigned_dorm": dorm_name}

        return {"assigned_dorm": None}

    except Exception as e:
        print("Error in dormitory assignment:", str(e))
        return {"assigned_dorm": None}

housing_manager_instructions = """
You are the Dormitory Housing Manager. Your job is to assign students to rooms based on personality and availability.
Each room can have a maximum of 2 students. If no compatible room is available, return "No available room."

Current room assignments:
{room_assignments}

New student profile:
{student_profile}
"""

def assign_students(state: HousingState):
    dorm = state.get("assigned_dorm", None)
    new_student = state["new_student"]
    
    if not dorm or dorm not in state['dorms']:
        print("No dormitory found for assignment.")
        return {"assigned_room": None}
    
    if isinstance(new_student, dict):
        new_student = Student(**new_student)
    
    room_assignments = "\n".join([f"{room}: {', '.join(occupants) if occupants else 'Empty'}" for room, occupants in state['dorms'][dorm].items()])
    student_profile = f"Name: {new_student.name}, Personality: {new_student.personality}"
    system_message = housing_manager_instructions.format(room_assignments=room_assignments, student_profile=student_profile)
    print("Assigning room in", dorm, "for student:", student_profile)
    print("Current room assignments:\n", room_assignments)
    
    response = llm.invoke([SystemMessage(content=system_message), HumanMessage(content="Assign the student to a room.")])
    
    try:
        result = response.content.strip()
        print("LLM Room Response:", result)
        
        if result == "No available room":
            return {"assigned_room": None}
        
        match = re.search(r'Room (\d+)', result)
        if match:
            room = f"Room {match.group(1)}"
        else:
            print("Could not extract room from LLM response.")
            return {"assigned_room": None}
        print(room)
        if room not in state['dorms'][dorm]:
            print("Not a valid room.")
            return {"assigned_room": None}
        
        print(f"Student {new_student.name} assigned to room {room} in dorm {dorm}")
        return {"assigned_room": room}
    except Exception as e:
        print("Error in room assignment:", str(e))
        return {"assigned_room": None}

# Define the graph
builder = StateGraph(HousingState, config_schema=configuration.Configuration)
builder.add_node("assign_dormitory", assign_dormitory)
builder.add_node("assign_students", assign_students)

builder.add_edge(START, "assign_dormitory")
builder.add_edge("assign_dormitory", "assign_students")
builder.add_edge("assign_students", END)

# Compile
graph = builder.compile()

# state = {
#     "dorms": {
#         "Dorm A": {
#             "Room 1": ["Alice (quiet)", "Bob (quiet)"],
#             "Room 2": ["Alice (quiet)", "Bob (quiet)"],
#             "Room 3": ["Alice (quiet)", "Bob (quiet)"],
#             "Room 4": ["Alice (quiet)", "Bob (quiet)"]
#         },
#         "Dorm C": {
#             "Room 1": [],
#             "Room 2": ["Dave (party)"],
#             "Room 3": []
#         },
#         "Dorm D": {
#             "Room 1": [],
#             "Room 2": [],
#             "Room 3": []
#         }
#     },
#     "new_student": Student(name="Eve", personality="Is very social and loves to party late at night."),
# }

# result = graph.invoke(state)
# print("Final result:", result)
