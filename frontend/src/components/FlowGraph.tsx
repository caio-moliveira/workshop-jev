import { Position, ReactFlow, type Edge, type Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { NODE_LABELS } from '../lib/questions'
import { NODES, takenEdges, type NodeStatus } from '../lib/runState'
import type { NodeName } from '../lib/types'

const STATUS_STYLE: Record<NodeStatus, { background: string; color: string; border: string }> = {
  waiting: { background: '#f8fafc', color: '#64748b', border: '#cbd5e1' },
  running: { background: '#e0e7ff', color: '#3730a3', border: '#6366f1' },
  done: { background: '#dcfce7', color: '#166534', border: '#22c55e' },
  skipped: { background: '#f1f5f9', color: '#94a3b8', border: '#e2e8f0' },
  blocked: { background: '#fee2e2', color: '#991b1b', border: '#ef4444' },
}

const STATUS_LABEL: Record<NodeStatus, string> = {
  waiting: 'aguardando',
  running: 'rodando',
  done: 'concluído',
  skipped: 'pulado',
  blocked: 'bloqueado',
}

const POSITION: Record<NodeName, { x: number; y: number }> = {
  guardrail: { x: 0, y: 70 },
  triage: { x: 200, y: 70 },
  reply: { x: 400, y: 0 },
  verify: { x: 600, y: 0 },
  act: { x: 800, y: 70 },
}

const EDGES: [NodeName, NodeName][] = [
  ['guardrail', 'triage'],
  ['guardrail', 'act'],
  ['triage', 'reply'],
  ['triage', 'act'],
  ['reply', 'verify'],
  ['reply', 'act'],
  ['verify', 'act'],
]

interface Props {
  statuses: Record<NodeName, NodeStatus>
  path: NodeName[]
  selected: NodeName | null
  onSelect: (node: NodeName) => void
}

export function FlowGraph({ statuses, path, selected, onSelect }: Props) {
  const taken = new Set(takenEdges(path))

  const nodes: Node[] = NODES.map((id) => {
    const style = STATUS_STYLE[statuses[id]]
    return {
      id,
      position: POSITION[id],
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      data: { label: `${NODE_LABELS[id]} · ${STATUS_LABEL[statuses[id]]}` },
      style: {
        ...style,
        border: `${selected === id ? 3 : 1}px solid ${style.border}`,
        borderRadius: 8,
        fontSize: 13,
        width: 150,
      },
    }
  })

  const edges: Edge[] = EDGES.map(([source, target]) => {
    const id = `${source}-${target}`
    const isTaken = taken.has(id)
    return {
      id,
      source,
      target,
      type: 'smoothstep',
      animated: isTaken && statuses[target] === 'running',
      style: {
        stroke: isTaken ? '#4f46e5' : '#cbd5e1',
        strokeWidth: isTaken ? 2.5 : 1,
      },
    }
  })

  return (
    <div className="h-56 rounded-lg border border-slate-200 bg-white">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        zoomOnScroll={false}
        panOnDrag={false}
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, node) => onSelect(node.id as NodeName)}
      />
    </div>
  )
}
