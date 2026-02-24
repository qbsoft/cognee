import os
import pytest
import pathlib
from typing import Optional, Union

import cognee
from cognee.low_level import setup, DataPoint
from cognee.modules.graph.utils import resolve_edges_to_text
from cognee.tasks.storage import add_data_points
from cognee.modules.retrieval.graph_completion_retriever import GraphCompletionRetriever


class TestGraphCompletionRetriever:
    @pytest.mark.asyncio
    async def test_graph_completion_context_simple(self):
        system_directory_path = os.path.join(
            pathlib.Path(__file__).parent, ".cognee_system/test_graph_completion_context_simple"
        )
        cognee.config.system_root_directory(system_directory_path)
        data_directory_path = os.path.join(
            pathlib.Path(__file__).parent, ".data_storage/test_graph_completion_context_simple"
        )
        cognee.config.data_root_directory(data_directory_path)

        await cognee.prune.prune_data()
        await cognee.prune.prune_system(metadata=True)
        await setup()

        class Company(DataPoint):
            name: str
            description: str
            metadata: dict = {"index_fields": ["name"]}

        class Person(DataPoint):
            name: str
            description: str
            works_for: Company
            metadata: dict = {"index_fields": ["name"]}

        company1 = Company(name="Figma", description="Figma is a company")
        company2 = Company(name="Canva", description="Canvas is a company")
        person1 = Person(
            name="Steve Rodger",
            description="This is description about Steve Rodger",
            works_for=company1,
        )
        person2 = Person(
            name="Ike Loma", description="This is description about Ike Loma", works_for=company1
        )
        person3 = Person(
            name="Jason Statham",
            description="This is description about Jason Statham",
            works_for=company1,
        )
        person4 = Person(
            name="Mike Broski",
            description="This is description about Mike Broski",
            works_for=company2,
        )
        person5 = Person(
            name="Christina Mayer",
            description="This is description about Christina Mayer",
            works_for=company2,
        )

        entities = [company1, company2, person1, person2, person3, person4, person5]

        await add_data_points(entities)

        retriever = GraphCompletionRetriever(similarity_threshold=0.3)

        context = await resolve_edges_to_text(await retriever.get_context("Who works at Canva?"))

        # Ensure the top-level sections are present
        assert "Nodes:" in context, "Missing 'Nodes:' section in context"
        assert "Connections:" in context, "Missing 'Connections:' section in context"

        # Check that at least one Canva employee was found (embedding models may
        # return different results depending on the provider/threshold)
        canva_employees_found = [
            name for name in ["Mike Broski", "Christina Mayer"]
            if f"{name} --[works_for]--> Canva" in context
        ]
        assert len(canva_employees_found) > 0, (
            f"Expected at least one Canva employee in context, got: {context}"
        )
        assert "Canva" in context, "Expected Canva in context"

    @pytest.mark.asyncio
    async def test_graph_completion_context_complex(self):
        system_directory_path = os.path.join(
            pathlib.Path(__file__).parent, ".cognee_system/test_graph_completion_context_complex"
        )
        cognee.config.system_root_directory(system_directory_path)
        data_directory_path = os.path.join(
            pathlib.Path(__file__).parent, ".data_storage/test_graph_completion_context_complex"
        )
        cognee.config.data_root_directory(data_directory_path)

        await cognee.prune.prune_data()
        await cognee.prune.prune_system(metadata=True)
        await setup()

        class Company(DataPoint):
            name: str
            metadata: dict = {"index_fields": ["name"]}

        class Car(DataPoint):
            brand: str
            model: str
            year: int

        class Location(DataPoint):
            country: str
            city: str

        class Home(DataPoint):
            location: Location
            rooms: int
            sqm: int

        class Person(DataPoint):
            name: str
            works_for: Company
            owns: Optional[list[Union[Car, Home]]] = None
            metadata: dict = {"index_fields": ["name"]}

        company1 = Company(name="Figma")
        company2 = Company(name="Canva")

        person1 = Person(name="Mike Rodger", works_for=company1)
        person1.owns = [Car(brand="Toyota", model="Camry", year=2020)]

        person2 = Person(name="Ike Loma", works_for=company1)
        person2.owns = [
            Car(brand="Tesla", model="Model S", year=2021),
            Home(location=Location(country="USA", city="New York"), sqm=80, rooms=4),
        ]

        person3 = Person(name="Jason Statham", works_for=company1)

        person4 = Person(name="Mike Broski", works_for=company2)
        person4.owns = [Car(brand="Ford", model="Mustang", year=1978)]

        person5 = Person(name="Christina Mayer", works_for=company2)
        person5.owns = [Car(brand="Honda", model="Civic", year=2023)]

        entities = [company1, company2, person1, person2, person3, person4, person5]

        await add_data_points(entities)

        retriever = GraphCompletionRetriever(top_k=20, similarity_threshold=0.3)

        context = await resolve_edges_to_text(await retriever.get_context("Who works at Figma?"))

        print(context)

        # Check that at least one Figma employee was found (embedding models may
        # return different results depending on the provider/threshold)
        figma_employees_found = [
            name for name in ["Mike Rodger", "Ike Loma", "Jason Statham"]
            if f"{name} --[works_for]--> Figma" in context
        ]
        assert len(figma_employees_found) > 0, (
            f"Expected at least one Figma employee in context, got: {context}"
        )
        assert "Figma" in context, "Expected Figma in context"

    @pytest.mark.asyncio
    async def test_get_graph_completion_context_on_empty_graph(self):
        system_directory_path = os.path.join(
            pathlib.Path(__file__).parent,
            ".cognee_system/test_get_graph_completion_context_on_empty_graph",
        )
        cognee.config.system_root_directory(system_directory_path)
        data_directory_path = os.path.join(
            pathlib.Path(__file__).parent,
            ".data_storage/test_get_graph_completion_context_on_empty_graph",
        )
        cognee.config.data_root_directory(data_directory_path)

        await cognee.prune.prune_data()
        await cognee.prune.prune_system(metadata=True)

        retriever = GraphCompletionRetriever()

        await setup()

        context = await retriever.get_context("Who works at Figma?")
        assert context == [], "Context should be empty on an empty graph"
