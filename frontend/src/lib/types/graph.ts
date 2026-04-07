export interface GraphNode {
  id: string;
  type_name: string;
  label: string;
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  source_id: string;
  target_id: string;
  link_type: string;
}

export interface GraphSnapshot {
  nodes: GraphNode[];
  edges: GraphEdge[];
  counts: Record<string, number>;
  edge_counts: Record<string, number>;
  total_nodes: number;
  total_edges: number;
}

export interface GraphSubgraph {
  center_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface OperationalNode {
  id: string;
  kind: "step" | "cause" | "effect" | "policy" | "signal" | "workflow";
  label: string;
  process: string;
  properties: Record<string, unknown>;
}

export interface OperationalEdge {
  source_id: string;
  target_id: string;
  link_type: string;
}

export interface OperationalGraph {
  nodes: OperationalNode[];
  edges: OperationalEdge[];
  processes: string[];
}
