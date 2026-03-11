"use client";

import { useCallback, useRef, useState, MutableRefObject } from "react";

import GraphVisualization, { GraphVisualizationAPI } from "../../(graph)/GraphVisualization";
import type { GraphControlsAPI } from "../../(graph)/GraphControls";
import CogneeAddWidget, { NodesAndLinks } from "../../(graph)/CogneeAddWidget";
import GraphLegend from "../../(graph)/GraphLegend";

interface GraphNode {
  id: string | number;
  label: string;
  properties?: object;
}

interface GraphData {
  nodes: GraphNode[];
  links: { source: string | number; target: string | number; label: string }[];
}

export default function GraphTab() {
  const [data, setData] = useState<GraphData>();

  const onDataChange = useCallback((newData: NodesAndLinks) => {
    if (newData === null) {
      setData(undefined);
      return;
    }

    if (!newData.nodes.length && !newData.links.length) {
      return;
    }

    setData(newData);
  }, []);

  const graphRef = useRef<GraphVisualizationAPI>();
  const graphControls = useRef<GraphControlsAPI>();

  return (
    <div className="h-full relative overflow-hidden bg-gray-50 rounded-xl m-2">
      <GraphVisualization
        key={data?.nodes.length}
        ref={graphRef as MutableRefObject<GraphVisualizationAPI>}
        data={data}
        graphControls={graphControls as MutableRefObject<GraphControlsAPI>}
        className="w-full h-full"
      />

      {/* Add widget overlay - top left */}
      <div className="absolute top-3 left-3 z-10 bg-white/90 backdrop-blur-sm rounded-xl shadow-lg p-4 w-80">
        <CogneeAddWidget onData={onDataChange} />
      </div>

      {/* Legend overlay - top right */}
      {data?.nodes.length && (
        <div className="absolute top-3 right-3 z-10 bg-white/90 backdrop-blur-sm rounded-xl shadow-lg p-4 w-48">
          <GraphLegend data={data?.nodes} />
        </div>
      )}

      {/* Stats bar - bottom center */}
      {(data?.nodes.length || data?.links.length) && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 bg-white/90 backdrop-blur-sm rounded-full shadow-lg px-6 py-2 flex items-center gap-6 text-sm text-gray-600">
          <span>Nodes: {data?.nodes.length || 0}</span>
          <span>Edges: {data?.links.length || 0}</span>
        </div>
      )}
    </div>
  );
}
