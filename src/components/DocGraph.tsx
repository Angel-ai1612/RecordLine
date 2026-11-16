import {
  BaseEdge,
  EdgeLabelRenderer,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  getBezierPath,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { motion, useReducedMotion } from "framer-motion";
import { useMemo, type KeyboardEvent as ReactKeyboardEvent } from "react";
import type { Document, Entity, Graph, Relationship } from "@/api/types";
import { FILE_LABEL, REL_LABEL, STATUS_LABEL } from "@/lib/format";

type DocData = {
  doc: Document;
  selected: boolean;
  index: number;
  interactive: boolean;
  onActivate?: () => void;
};
type EntData = { entity: Entity; selected: boolean; index: number; onActivate?: () => void };
type RelData = {
  rel: Relationship;
  selected: boolean;
  showLabel: boolean;
  ariaLabel: string;
  onActivate?: () => void;
};

function activateWithKeyboard(event: ReactKeyboardEvent, action: (() => void) | undefined) {
  if (!action || (event.key !== "Enter" && event.key !== " ")) return;
  event.preventDefault();
  event.stopPropagation();
  action();
}

function useDrift(index: number) {
  const reduce = useReducedMotion();
  if (reduce) return {};
  const amp = 4 + (index % 3) * 2;
  return {
    animate: { x: [0, amp, 0, -amp, 0], y: [0, -amp, 0, amp * 0.6, 0] },
    transition: { duration: 14 + (index % 4) * 3, repeat: Infinity, ease: "easeInOut" as const },
  };
}

function DocNode({ data }: NodeProps<Node<DocData>>) {
  const { doc, selected, index } = data;
  const drift = useDrift(index);
  const busy = doc.status !== "ready" && doc.status !== "failed";
  return (
    <motion.div {...drift}>
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />
      <motion.button
        type="button"
        aria-label={`Document ${doc.filename}, ${STATUS_LABEL[doc.status]}. Inspect evidence`}
        onClick={(event) => {
          event.stopPropagation();
          data.onActivate?.();
        }}
        onKeyDown={(event) => activateWithKeyboard(event, data.onActivate)}
        {...(data.interactive ? { layoutId: `node-${doc.id}` } : {})}
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.1 + index * 0.08 }}
        className={`paper-surface w-[200px] px-4 py-3 text-left ${selected ? "outline outline-2 outline-offset-2 outline-signal" : ""}`}
      >
        <div className="flex items-center justify-between font-mono text-[0.6rem] uppercase tracking-wider text-paper-muted">
          <span>{FILE_LABEL[doc.fileType]}</span>
          <span className={doc.status === "failed" ? "text-signal" : ""}>
            {busy || doc.status === "failed" ? STATUS_LABEL[doc.status] : doc.fileDate}
          </span>
        </div>
        <div className="mt-1.5 truncate font-display text-[0.95rem]">{doc.filename}</div>
        {busy && (
          <div className="mt-2 h-px w-full bg-paper-border">
            <motion.div
              className="h-px bg-signal"
              animate={{ width: ["0%", "100%"] }}
              transition={{ duration: 1.6, repeat: Infinity }}
            />
          </div>
        )}
      </motion.button>
    </motion.div>
  );
}

function EntityNode({ data }: NodeProps<Node<EntData>>) {
  const drift = useDrift(data.index + 2);
  return (
    <motion.div {...drift}>
      <Handle type="target" position={Position.Top} />
      <Handle type="source" position={Position.Bottom} />
      <motion.button
        type="button"
        aria-label={`${data.entity.type} entity ${data.entity.name}. Inspect evidence`}
        onClick={(event) => {
          event.stopPropagation();
          data.onActivate?.();
        }}
        onKeyDown={(event) => activateWithKeyboard(event, data.onActivate)}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 + data.index * 0.06 }}
        className={`border bg-background px-2.5 py-1 font-mono text-[0.65rem] uppercase tracking-wider ${
          data.selected ? "border-signal text-signal" : "border-hairline text-muted-foreground"
        }`}
      >
        {data.entity.name}
      </motion.button>
    </motion.div>
  );
}

function RelEdge(props: EdgeProps<Edge<RelData>>) {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, id } = props;
  const [path, lx, ly] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });
  const reduce = useReducedMotion();
  if (!data) return null;
  const { rel, selected, showLabel } = data;
  const isConflict = rel.type === "contradicts";
  const stroke = isConflict
    ? "var(--warning)"
    : selected
      ? "var(--signal)"
      : rel.reviewStatus === "rejected"
        ? "var(--destructive)"
        : "var(--faint)";
  return (
    <>
      <BaseEdge id={`${id}-hit`} path={path} style={{ stroke: "transparent", strokeWidth: 18 }} />
      <motion.path
        d={path}
        fill="none"
        stroke={stroke}
        strokeWidth={selected ? 2 : 1 + rel.score}
        strokeDasharray={rel.reviewStatus === "pending" ? "5 5" : undefined}
        initial={reduce ? false : { pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: rel.reviewStatus === "rejected" ? 0.4 : 1 }}
        transition={{ duration: 1.2, ease: "easeInOut", delay: 0.4 }}
        style={{ pointerEvents: "none" }}
      />
      {showLabel && (
        <EdgeLabelRenderer>
          <button
            type="button"
            aria-label={data.ariaLabel}
            onClick={(event) => {
              event.stopPropagation();
              data.onActivate?.();
            }}
            onKeyDown={(event) => activateWithKeyboard(event, data.onActivate)}
            className={`nodrag nopan absolute border bg-background px-1.5 py-0.5 font-mono text-[0.6rem] ${
              selected || isConflict
                ? "border-signal text-signal"
                : "border-hairline text-muted-foreground"
            }`}
            style={{
              transform: `translate(-50%, -50%) translate(${lx}px, ${ly}px)`,
              pointerEvents: "all",
            }}
          >
            {Math.round(rel.score * 100)}
          </button>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const nodeTypes = { doc: DocNode, entity: EntityNode };
const edgeTypes = { rel: RelEdge };

export interface DocGraphProps {
  graph: Graph;
  showEntities?: boolean;
  selectedId?: string | null;
  interactive?: boolean;
  visibleRelIds?: Set<string>;
  onSelectDoc?: (d: Document) => void;
  onSelectEntity?: (e: Entity) => void;
  onSelectRel?: (r: Relationship) => void;
}

function Inner({
  graph,
  showEntities = true,
  selectedId,
  interactive = true,
  visibleRelIds,
  onSelectDoc,
  onSelectEntity,
  onSelectRel,
}: DocGraphProps) {
  const { nodes, edges } = useMemo(() => {
    const ready = new Set(graph.documents.filter((d) => d.status === "ready").map((d) => d.id));
    const documentsById = new Map(graph.documents.map((document) => [document.id, document]));

    const nodes: Node[] = graph.documents.map((doc, index) => {
      const angle = (index * Math.PI * 2) / Math.max(graph.documents.length, 1);
      const pos = { x: 450 + Math.cos(angle) * 380, y: 320 + Math.sin(angle) * 280 };
      return {
        id: doc.id,
        type: "doc",
        position: pos,
        data: {
          doc,
          selected: selectedId === doc.id,
          index,
          interactive,
          onActivate: onSelectDoc ? () => onSelectDoc(doc) : undefined,
        },
        focusable: false,
      };
    });
    const edges: Edge[] = graph.relationships
      .filter((r) => ready.has(r.sourceDocId) && ready.has(r.targetDocId))
      .filter((r) => !visibleRelIds || visibleRelIds.has(r.id))
      .map((rel) => {
        const source = documentsById.get(rel.sourceDocId)?.filename ?? rel.sourceDocId;
        const target = documentsById.get(rel.targetDocId)?.filename ?? rel.targetDocId;
        const ariaLabel = `${REL_LABEL[rel.type]} relationship from ${source} to ${target}, score ${Math.round(rel.score * 100)} percent. Inspect evidence`;
        return {
          id: rel.id,
          source: rel.sourceDocId,
          target: rel.targetDocId,
          type: "rel",
          data: {
            rel,
            selected: selectedId === rel.id,
            showLabel: true,
            ariaLabel,
            onActivate: onSelectRel ? () => onSelectRel(rel) : undefined,
          },
          focusable: false,
        };
      });
    if (showEntities) {
      graph.entities.forEach((entity, index) => {
        nodes.push({
          id: entity.id,
          type: "entity",
          position: { x: 290 + (index % 3) * 160, y: 210 + Math.floor(index / 3) * 130 },
          data: {
            entity,
            selected: selectedId === entity.id,
            index,
            onActivate: onSelectEntity ? () => onSelectEntity(entity) : undefined,
          },
          focusable: false,
        });
        entity.documentIds
          .filter((d) => ready.has(d))
          .forEach((d) =>
            edges.push({
              id: `m-${entity.id}-${d}`,
              source: entity.id,
              target: d,
              style: { stroke: "var(--hairline)", strokeWidth: 1 },
              selectable: false,
              focusable: false,
            }),
          );
      });
    }
    return { nodes, edges };
  }, [
    graph,
    showEntities,
    selectedId,
    interactive,
    visibleRelIds,
    onSelectDoc,
    onSelectEntity,
    onSelectRel,
  ]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      fitView
      fitViewOptions={{ padding: 0.06 }}
      minZoom={0.25}
      maxZoom={2.5}
      nodesDraggable={interactive}
      nodesConnectable={false}
      panOnDrag={interactive}
      zoomOnScroll={interactive}
      zoomOnPinch={interactive}
      zoomOnDoubleClick={false}
      preventScrolling={false}
      proOptions={{ hideAttribution: true }}
      onNodeClick={(_, n) => {
        if (n.type === "doc") onSelectDoc?.((n.data as DocData).doc);
        else if (n.type === "entity") onSelectEntity?.((n.data as EntData).entity);
      }}
      onEdgeClick={(_, e) => e.type === "rel" && onSelectRel?.((e.data as RelData).rel)}
    />
  );
}

export function DocGraph(props: DocGraphProps) {
  return (
    <ReactFlowProvider>
      <Inner {...props} />
    </ReactFlowProvider>
  );
}
