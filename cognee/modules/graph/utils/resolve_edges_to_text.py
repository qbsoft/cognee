from typing import List, Dict, Any
from cognee.modules.graph.cognee_graph.CogneeGraphElements import Edge


async def resolve_edges_to_context(retrieved_edges: List[Edge]) -> List[Dict[str, Any]]:
    """
    Converts retrieved graph edges into structured context with source tracing information.
    
    This function extracts nodes from edges and returns their content along with
    source file information (file path, line numbers, etc.) for precise reference.

    Parameters:
    -----------
        - retrieved_edges (list): A list of edges retrieved from the graph.

    Returns:
    --------
        - List[Dict]: A list of context dictionaries, each containing:
            - text: The node content text
            - source_file_path: Original source file path (if available)
            - source_data_id: Source data UUID (if available)
            - start_line: Starting line number (if available)
            - end_line: Ending line number (if available)
            - start_char: Starting character offset (if available)
            - end_char: Ending character offset (if available)
            - chunk_index: Chunk index in the document (if available)
            - page_number: Page number (if available)
            - node_type: Type of the node
    """
    contexts = []
    seen_nodes = set()
    
    for edge in retrieved_edges:
        for node in (edge.node1, edge.node2):
            if node.id in seen_nodes:
                continue
            seen_nodes.add(node.id)
            
            # Extract text content
            text = node.attributes.get("text")
            if not text:
                text = node.attributes.get("description") or node.attributes.get("name", "")
            
            # Only include nodes with meaningful content
            if not text or len(text.strip()) < 10:
                continue
            
            # Build context with source tracing information
            context = {
                "text": text,
                "node_type": node.attributes.get("type", "unknown"),
            }
            
            # Extract additional properties from the 'properties' JSON field if present
            # (Kuzu stores non-core attributes in a serialized JSON field)
            import json
            properties_json = node.attributes.get("properties")
            additional_props = {}
            if properties_json and isinstance(properties_json, str):
                try:
                    additional_props = json.loads(properties_json)
                except json.JSONDecodeError:
                    pass
            
            # Add source tracing fields from both attributes and properties JSON
            # Check both node.attributes (for direct access) and additional_props (from JSON)
            if "source_file_path" in node.attributes:
                context["source_file_path"] = node.attributes["source_file_path"]
            elif "source_file_path" in additional_props:
                context["source_file_path"] = additional_props["source_file_path"]
            
            if "source_data_id" in node.attributes:
                context["source_data_id"] = str(node.attributes["source_data_id"])
            elif "source_data_id" in additional_props:
                context["source_data_id"] = str(additional_props["source_data_id"])
            
            if "start_line" in node.attributes:
                context["start_line"] = node.attributes["start_line"]
            elif "start_line" in additional_props:
                context["start_line"] = additional_props["start_line"]
            
            if "end_line" in node.attributes:
                context["end_line"] = node.attributes["end_line"]
            elif "end_line" in additional_props:
                context["end_line"] = additional_props["end_line"]
            
            if "chunk_index" in node.attributes:
                context["chunk_index"] = node.attributes["chunk_index"]
            elif "chunk_index" in additional_props:
                context["chunk_index"] = additional_props["chunk_index"]
            
            if "page_number" in node.attributes:
                context["page_number"] = node.attributes["page_number"]
            elif "page_number" in additional_props:
                context["page_number"] = additional_props["page_number"]
            
            # Add character offset fields for precise scrolling
            if "start_char" in node.attributes:
                context["start_char"] = node.attributes["start_char"]
            elif "start_char" in additional_props:
                context["start_char"] = additional_props["start_char"]
            
            if "end_char" in node.attributes:
                context["end_char"] = node.attributes["end_char"]
            elif "end_char" in additional_props:
                context["end_char"] = additional_props["end_char"]
            
            contexts.append(context)
    
    return contexts


async def resolve_edges_to_text(retrieved_edges: List[Edge]) -> str:
    """
    Converts retrieved graph edges into a human-readable string format.

    Parameters:
    -----------

        - retrieved_edges (list): A list of edges retrieved from the graph.

    Returns:
    --------

        - str: A formatted string representation of the nodes and their connections.
    """

    def _get_nodes(retrieved_edges: List[Edge]) -> dict:
        def _get_title(text: str, first_n_words: int = 7, top_n_words: int = 3) -> str:
            def _top_n_words(text, stop_words=None, top_n=3, separator=", "):
                """Concatenates the top N frequent words in text."""
                if stop_words is None:
                    from cognee.modules.retrieval.utils.stop_words import DEFAULT_STOP_WORDS

                    stop_words = DEFAULT_STOP_WORDS

                import string

                words = [word.lower().strip(string.punctuation) for word in text.split()]

                if stop_words:
                    words = [word for word in words if word and word not in stop_words]

                from collections import Counter

                top_words = [word for word, freq in Counter(words).most_common(top_n)]

                return separator.join(top_words)

            """Creates a title, by combining first words with most frequent words from the text."""
            first_words = text.split()[:first_n_words]
            top_words = _top_n_words(text, top_n=first_n_words)
            return f"{' '.join(first_words)}... [{top_words}]"

        """Creates a dictionary of nodes with their names and content."""
        nodes = {}
        for edge in retrieved_edges:
            for node in (edge.node1, edge.node2):
                if node.id not in nodes:
                    text = node.attributes.get("text")
                    if text:
                        name = _get_title(text)
                        content = text
                    else:
                        name = node.attributes.get("name", "Unnamed Node")
                        content = node.attributes.get("description", name)
                    nodes[node.id] = {"node": node, "name": name, "content": content}
        return nodes

    nodes = _get_nodes(retrieved_edges)
    node_section = "\n".join(
        f"Node: {info['name']}\n__node_content_start__\n{info['content']}\n__node_content_end__\n"
        for info in nodes.values()
    )
    connection_section = "\n".join(
        f"{nodes[edge.node1.id]['name']} --[{edge.attributes['relationship_type']}]--> {nodes[edge.node2.id]['name']}"
        for edge in retrieved_edges
    )
    return f"Nodes:\n{node_section}\n\nConnections:\n{connection_section}"
