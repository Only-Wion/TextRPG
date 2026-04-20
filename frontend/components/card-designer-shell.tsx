"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent, WheelEvent as ReactWheelEvent } from "react";

import {
  createDesignerAgentSession,
  createDesignerPack,
  deleteDesignerCard,
  getDesignerCards,
  getDesignerCardTemplate,
  getDesignerCardTypes,
  getDesignerCanvasState,
  loadDesignerCard,
  saveDesignerCard,
  saveDesignerCanvasState,
  sendDesignerAgentMessage,
  validateDesignerCard,
} from "../lib/api";
import type {
  AuthUser,
  CanvasWorkspaceState,
  DesignerAgentSession,
  DesignerCardPayload,
  DesignerCardSummary,
  PackRecord,
} from "../lib/api-contract";
import { AppSidebar } from "./app-sidebar";

type CardDesignerShellProps = {
  packs: PackRecord[];
  currentUser: AuthUser;
};

type CreatePackDraft = {
  pack_id: string;
  name: string;
  version: string;
  author: string;
  description: string;
};

type CardEditorDraft = {
  tabId: string;
  title: string;
  originalPath: string;
  cardType: string;
  customCardType: string;
  cardId: string;
  folderPath: string;
  frontmatterText: string;
  body: string;
};

type CardEditorTab = {
  id: string;
  title: string;
  draft: CardEditorDraft;
};

type TreeFolder = {
  path: string;
  name: string;
  parentPath: string;
  depth: number;
};

type CanvasNode = {
  id: string;
  cardPath: string;
  title: string;
  cardType: string;
  x: number;
  y: number;
};

type CanvasEdge = {
  id: string;
  fromId: string;
  toId: string;
  label: string;
};

type CanvasPoint = {
  x: number;
  y: number;
};

type CanvasNodeGeometry = {
  cx: number;
  cy: number;
  width: number;
  height: number;
};

type DragState =
  | {
      type: "node";
      nodeId: string;
      pointerX: number;
      pointerY: number;
      originX: number;
      originY: number;
    }
  | {
      type: "pan";
      pointerX: number;
      pointerY: number;
      originX: number;
      originY: number;
    }
  | null;

const CANVAS_TAB_ID = "canvas";
const CREATE_PACK_TAB_ID = "create-pack";
const CONNECT_PICK_SOURCE_ID = "__pick_source__";

function normalizeCanvasState(payload: Partial<CanvasWorkspaceState> | null): CanvasWorkspaceState {
  return {
    canvas_nodes: Array.isArray(payload?.canvas_nodes) ? payload!.canvas_nodes : [],
    canvas_edges: Array.isArray(payload?.canvas_edges) ? payload!.canvas_edges : [],
    canvas_offset: {
      x: Number(payload?.canvas_offset?.x ?? 0),
      y: Number(payload?.canvas_offset?.y ?? 0),
    },
    canvas_scale: Number(payload?.canvas_scale ?? 1) || 1,
    selected_node_id: typeof payload?.selected_node_id === "string" ? payload.selected_node_id : null,
    selected_edge_id: typeof payload?.selected_edge_id === "string" ? payload.selected_edge_id : null,
    connect_source_id: typeof payload?.connect_source_id === "string" ? payload.connect_source_id : null,
  };
}

function canvasStateFromRuntime(
  canvasNodes: CanvasNode[],
  canvasEdges: CanvasEdge[],
  canvasOffset: { x: number; y: number },
  canvasScale: number,
  selectedNodeId: string | null,
  selectedEdgeId: string | null,
  connectSourceId: string | null,
): CanvasWorkspaceState {
  return {
    canvas_nodes: canvasNodes as Array<Record<string, unknown>>,
    canvas_edges: canvasEdges as Array<Record<string, unknown>>,
    canvas_offset: canvasOffset,
    canvas_scale: canvasScale,
    selected_node_id: selectedNodeId,
    selected_edge_id: selectedEdgeId,
    connect_source_id: connectSourceId,
  };
}

function canvasNodeFallbackCenter(node: CanvasNode, canvasOffset: { x: number; y: number }, canvasScale: number): CanvasPoint {
  return {
    x: node.x * canvasScale + canvasOffset.x + 112,
    y: node.y * canvasScale + canvasOffset.y + 60,
  };
}

function canvasNodeFallbackGeometry(
  node: CanvasNode,
  canvasOffset: { x: number; y: number },
  canvasScale: number,
): CanvasNodeGeometry {
  const center = canvasNodeFallbackCenter(node, canvasOffset, canvasScale);
  return {
    cx: center.x,
    cy: center.y,
    width: 224 * canvasScale,
    height: 120 * canvasScale,
  };
}

function getRectangleAnchorPoint(source: CanvasNodeGeometry, target: CanvasNodeGeometry): CanvasPoint {
  const dx = target.cx - source.cx;
  const dy = target.cy - source.cy;
  if (dx === 0 && dy === 0) {
    return { x: source.cx, y: source.cy };
  }

  const halfWidth = source.width / 2;
  const halfHeight = source.height / 2;
  const tx = Math.abs(dx) > 0 ? halfWidth / Math.abs(dx) : Number.POSITIVE_INFINITY;
  const ty = Math.abs(dy) > 0 ? halfHeight / Math.abs(dy) : Number.POSITIVE_INFINITY;
  const ratio = Math.min(tx, ty);

  return {
    x: source.cx + dx * ratio,
    y: source.cy + dy * ratio,
  };
}

function stringifyFrontmatter(payload: Record<string, unknown>): string {
  return JSON.stringify(payload, null, 2);
}

function createEmptyPackDraft(): CreatePackDraft {
  return {
    pack_id: "",
    name: "",
    version: "0.1.0",
    author: "",
    description: "",
  };
}

function createBlankCardDraft(overrides: Partial<CardEditorDraft> = {}): CardEditorDraft {
  return {
    tabId: `draft-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    title: "New Card",
    originalPath: "",
    cardType: "card",
    customCardType: "",
    cardId: "",
    folderPath: "",
    frontmatterText: "{}",
    body: "",
    ...overrides,
  };
}

function normalizePath(value: string): string {
  return String(value || "")
    .replace(/\\+/g, "/")
    .replace(/^\/+|\/+$/g, "")
    .trim();
}

function pluralizeType(cardType: string): string {
  const normalized = normalizePath(cardType);
  if (!normalized) {
    return "cards";
  }
  if (normalized === "memory") {
    return "memories";
  }
  if (normalized.endsWith("s")) {
    return normalized;
  }
  return `${normalized}s`;
}

function singularizeCategory(category: string): string {
  const normalized = normalizePath(category);
  if (!normalized) {
    return "card";
  }
  if (normalized === "memories") {
    return "memory";
  }
  if (normalized.endsWith("s") && normalized.length > 1) {
    return normalized.slice(0, -1);
  }
  return normalized;
}

function formatFolderTarget(cardType: string, folderPath: string): string {
  const category = pluralizeType(cardType);
  const nested = normalizePath(folderPath);
  return nested ? `${category}/${nested}` : category;
}

function splitTreeFolder(fullFolderPath: string): { category: string; nestedFolder: string } {
  const normalized = normalizePath(fullFolderPath);
  if (!normalized) {
    return { category: "", nestedFolder: "" };
  }
  const parts = normalized.split("/");
  return {
    category: parts[0] ?? "",
    nestedFolder: parts.slice(1).join("/"),
  };
}

function fullFolderPathFromCard(card: DesignerCardSummary): string {
  const category = normalizePath(card.category);
  const folder = normalizePath(card.folder_path);
  return folder ? `${category}/${folder}` : category;
}

function parsePendingBatchSavePreview(content: string) {
  if (!content.includes("batch_save_cards")) {
    return null;
  }
  const line = content
    .split("\n")
    .map((item) => item.trim())
    .find((item) => item.startsWith("- batch_save_cards:"));
  if (!line) {
    return null;
  }
  const jsonText = line.slice("- batch_save_cards:".length).trim();
  if (!jsonText) {
    return null;
  }
  try {
    const payload = JSON.parse(jsonText) as {
      pack_id?: unknown;
      cards?: Array<{
        card_type?: unknown;
        card_id?: unknown;
        frontmatter?: { title?: unknown; name?: unknown; tags?: unknown };
        body?: unknown;
      }>;
    };
    const cards = Array.isArray(payload.cards)
      ? payload.cards.map((card) => {
          const frontmatter = card.frontmatter ?? {};
          const rawTags = frontmatter.tags;
          return {
            title: String(frontmatter.title ?? frontmatter.name ?? card.card_id ?? "untitled"),
            card_type: String(card.card_type ?? "card"),
            card_id: String(card.card_id ?? "unknown"),
            tags: Array.isArray(rawTags) ? rawTags.map((tag) => String(tag)) : [],
            body: String(card.body ?? ""),
          };
        })
      : [];
    return {
      pack_id: String(payload.pack_id ?? ""),
      cards,
    };
  } catch {
    return null;
  }
}

function buildFolderList(cards: DesignerCardSummary[], cardTypes: string[], localFolders: string[]): TreeFolder[] {
  const allFolders = new Set<string>();

  for (const cardType of cardTypes) {
    allFolders.add(pluralizeType(cardType));
  }

  for (const card of cards) {
    const fullPath = fullFolderPathFromCard(card);
    const parts = normalizePath(fullPath).split("/").filter(Boolean);
    let current = "";
    for (const part of parts) {
      current = current ? `${current}/${part}` : part;
      allFolders.add(current);
    }
  }

  for (const localFolder of localFolders) {
    const parts = normalizePath(localFolder).split("/").filter(Boolean);
    let current = "";
    for (const part of parts) {
      current = current ? `${current}/${part}` : part;
      allFolders.add(current);
    }
  }

  return Array.from(allFolders)
    .filter(Boolean)
    .sort((a, b) => a.localeCompare(b))
    .map((path) => {
      const parts = path.split("/").filter(Boolean);
      return {
        path,
        name: parts[parts.length - 1] ?? path,
        parentPath: parts.slice(0, -1).join("/"),
        depth: Math.max(0, parts.length - 1),
      };
    });
}

function buildInitialDraftFromPayload(payload: DesignerCardPayload): CardEditorDraft {
  return createBlankCardDraft({
    title: payload.card_id,
    originalPath: payload.path,
    cardType: payload.card_type,
    cardId: payload.card_id,
    folderPath: payload.folder_path || "",
    frontmatterText: stringifyFrontmatter(payload.frontmatter),
    body: payload.body,
  });
}

export function CardDesignerShell({ packs, currentUser }: CardDesignerShellProps) {
  const [runtimePacks, setRuntimePacks] = useState(packs);
  const [selectedPackId, setSelectedPackId] = useState(packs[0]?.pack_id ?? "");
  const [cardTypes, setCardTypes] = useState<string[]>([]);
  const [cards, setCards] = useState<DesignerCardSummary[]>([]);
  const [localFolders, setLocalFolders] = useState<string[]>([]);
  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({});
  const [editorTabs, setEditorTabs] = useState<CardEditorTab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string>(packs.length > 0 ? CANVAS_TAB_ID : CREATE_PACK_TAB_ID);
  const [createPackDraft, setCreatePackDraft] = useState<CreatePackDraft>(createEmptyPackDraft());
  const [keyword, setKeyword] = useState("");
  const [agentSession, setAgentSession] = useState<DesignerAgentSession | null>(null);
  const [agentInput, setAgentInput] = useState("");
  const [toolLogs, setToolLogs] = useState<string[]>([]);
  const [isBusy, setIsBusy] = useState(false);
  const [isCardsLoading, setIsCardsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [canvasNodes, setCanvasNodes] = useState<CanvasNode[]>([]);
  const [canvasEdges, setCanvasEdges] = useState<CanvasEdge[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [connectSourceId, setConnectSourceId] = useState<string | null>(null);
  const [canvasOffset, setCanvasOffset] = useState({ x: 0, y: 0 });
  const [canvasScale, setCanvasScale] = useState(1);
  const [canvasHydrated, setCanvasHydrated] = useState(false);
  const [canvasNodeGeometry, setCanvasNodeGeometry] = useState<Record<string, CanvasNodeGeometry>>({});

  const viewportRef = useRef<HTMLDivElement | null>(null);
  const canvasNodeRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const dragStateRef = useRef<DragState>(null);
  const canvasSaveTimerRef = useRef<number | null>(null);
  const hydratedPackIdRef = useRef<string>("");

  const agentHistory = useMemo(() => {
    const history = agentSession?.state?.history;
    return Array.isArray(history) ? history : [];
  }, [agentSession]);

  const agentTargetPackId = useMemo(() => {
    const sessionPackId = String(agentSession?.selected_pack_id ?? "").trim();
    if (sessionPackId) {
      return sessionPackId;
    }
    const statePackId = String((agentSession?.state as { selected_pack_id?: unknown } | undefined)?.selected_pack_id ?? "").trim();
    return statePackId || selectedPackId;
  }, [agentSession, selectedPackId]);

  const agentTargetPackName = useMemo(() => {
    const record = runtimePacks.find((pack) => pack.pack_id === agentTargetPackId);
    return record?.name ?? "Unknown";
  }, [agentTargetPackId, runtimePacks]);

  const activeEditorTab = useMemo(
    () => editorTabs.find((tab) => tab.id === activeTabId) ?? null,
    [activeTabId, editorTabs],
  );

  const folderList = useMemo(() => buildFolderList(cards, cardTypes, localFolders), [cardTypes, cards, localFolders]);

  const cardsByFolder = useMemo(() => {
    const map = new Map<string, DesignerCardSummary[]>();
    for (const card of cards) {
      const folder = fullFolderPathFromCard(card);
      const items = map.get(folder) ?? [];
      items.push(card);
      map.set(folder, items);
    }
    for (const entry of map.values()) {
      entry.sort((a, b) => a.title.localeCompare(b.title));
    }
    return map;
  }, [cards]);

  const folderChildren = useMemo(() => {
    const map = new Map<string, TreeFolder[]>();
    for (const folder of folderList) {
      const items = map.get(folder.parentPath) ?? [];
      items.push(folder);
      map.set(folder.parentPath, items);
    }
    for (const entry of map.values()) {
      entry.sort((a, b) => a.name.localeCompare(b.name));
    }
    return map;
  }, [folderList]);

  const keywordLower = keyword.trim().toLowerCase();

  const visibleFolderPaths = useMemo(() => {
    if (!keywordLower) {
      return new Set(folderList.map((folder) => folder.path));
    }
    const visible = new Set<string>();
    for (const folder of folderList) {
      if (folder.path.toLowerCase().includes(keywordLower)) {
        let current = folder.path;
        while (current) {
          visible.add(current);
          current = current.split("/").slice(0, -1).join("/");
        }
      }
    }
    for (const card of cards) {
      const haystack = [card.title, card.card_id, card.path, card.card_type].join(" ").toLowerCase();
      if (!haystack.includes(keywordLower)) {
        continue;
      }
      const folderPath = fullFolderPathFromCard(card);
      visible.add(folderPath);
      let current = folderPath;
      while (current) {
        visible.add(current);
        current = current.split("/").slice(0, -1).join("/");
      }
    }
    return visible;
  }, [cards, folderList, keywordLower]);

  useEffect(() => {
    if (runtimePacks.length === 0) {
      setSelectedPackId("");
      setActiveTabId(CREATE_PACK_TAB_ID);
      return;
    }
    if (!runtimePacks.some((pack) => pack.pack_id === selectedPackId)) {
      setSelectedPackId(runtimePacks[0]?.pack_id ?? "");
    }
  }, [runtimePacks, selectedPackId]);

  useEffect(() => {
    if (!selectedPackId) {
      hydratedPackIdRef.current = "";
      setCanvasHydrated(true);
      setCards([]);
      setCardTypes([]);
      return;
    }
    let cancelled = false;
    async function loadDesignerData() {
      setIsCardsLoading(true);
      try {
        const [nextTypes, nextCards] = await Promise.all([
          getDesignerCardTypes(selectedPackId),
          getDesignerCards(selectedPackId),
        ]);
        if (cancelled) {
          return;
        }
        setCardTypes(nextTypes.length > 0 ? nextTypes : ["card"]);
        setCards(nextCards);
        setLocalFolders([]);
        setExpandedFolders(
          Object.fromEntries(
            buildFolderList(nextCards, nextTypes, []).map((folder) => [folder.path, folder.depth <= 1]),
          ),
        );
        setEditorTabs([]);
        setCanvasHydrated(false);
        const savedSnapshot = normalizeCanvasState(await getDesignerCanvasState(selectedPackId));
        setCanvasNodes(savedSnapshot.canvas_nodes as CanvasNode[]);
        setCanvasEdges(savedSnapshot.canvas_edges as CanvasEdge[]);
        setSelectedNodeId(savedSnapshot.selected_node_id);
        setSelectedEdgeId(savedSnapshot.selected_edge_id);
        setConnectSourceId(savedSnapshot.connect_source_id);
        setCanvasOffset(savedSnapshot.canvas_offset);
        setCanvasScale(savedSnapshot.canvas_scale);
        hydratedPackIdRef.current = selectedPackId;
        setCanvasHydrated(true);
        setActiveTabId(CANVAS_TAB_ID);
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : "Failed to load designer data.");
        }
      } finally {
        if (!cancelled) {
          setIsCardsLoading(false);
        }
      }
    }
    void loadDesignerData();
    return () => {
      cancelled = true;
    };
  }, [currentUser.id, selectedPackId]);

  useEffect(() => {
    if (!canvasHydrated || !selectedPackId || hydratedPackIdRef.current !== selectedPackId) {
      return;
    }
    if (canvasSaveTimerRef.current) {
      window.clearTimeout(canvasSaveTimerRef.current);
    }
    canvasSaveTimerRef.current = window.setTimeout(() => {
      void saveDesignerCanvasState(
        selectedPackId,
        canvasStateFromRuntime(
          canvasNodes,
          canvasEdges,
          canvasOffset,
          canvasScale,
          selectedNodeId,
          selectedEdgeId,
          connectSourceId,
        ),
      ).catch((error) => {
        setErrorMessage(error instanceof Error ? error.message : "Failed to save canvas state.");
      });
    }, 250);
    return () => {
      if (canvasSaveTimerRef.current) {
        window.clearTimeout(canvasSaveTimerRef.current);
      }
    };
  }, [
    canvasEdges,
    canvasHydrated,
    canvasNodes,
    canvasOffset,
    canvasScale,
    connectSourceId,
    selectedEdgeId,
    selectedNodeId,
    selectedPackId,
  ]);

  useEffect(() => {
    if (!selectedPackId || agentSession) {
      return;
    }
    let cancelled = false;
    async function bootstrapAgentSession() {
      try {
        const session = await createDesignerAgentSession(selectedPackId);
        if (!cancelled) {
          setAgentSession(session);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : "Failed to initialize designer agent.");
        }
      }
    }
    void bootstrapAgentSession();
    return () => {
      cancelled = true;
    };
  }, [agentSession, selectedPackId]);

  useEffect(() => {
    function handlePointerMove(event: MouseEvent) {
      const dragState = dragStateRef.current;
      if (!dragState) {
        return;
      }
      if (dragState.type === "node") {
        const deltaX = (event.clientX - dragState.pointerX) / canvasScale;
        const deltaY = (event.clientY - dragState.pointerY) / canvasScale;
        setCanvasNodes((current) =>
          current.map((node) =>
            node.id === dragState.nodeId
              ? {
                  ...node,
                  x: dragState.originX + deltaX,
                  y: dragState.originY + deltaY,
                }
              : node,
          ),
        );
        return;
      }
      setCanvasOffset({
        x: dragState.originX + (event.clientX - dragState.pointerX),
        y: dragState.originY + (event.clientY - dragState.pointerY),
      });
    }

    function handlePointerUp() {
      dragStateRef.current = null;
    }

    window.addEventListener("mousemove", handlePointerMove);
    window.addEventListener("mouseup", handlePointerUp);
    return () => {
      window.removeEventListener("mousemove", handlePointerMove);
      window.removeEventListener("mouseup", handlePointerUp);
    };
  }, [canvasScale]);

  useLayoutEffect(() => {
    if (!canvasHydrated || !viewportRef.current) {
      return;
    }

    function measureCanvasNodeCenters() {
      const viewport = viewportRef.current;
      if (!viewport) {
        return;
      }
      const viewportRect = viewport.getBoundingClientRect();
      const nextGeometry: Record<string, CanvasNodeGeometry> = {};
      for (const node of canvasNodes) {
        const element = canvasNodeRefs.current[node.id];
        if (!element) {
          continue;
        }
        const rect = element.getBoundingClientRect();
        nextGeometry[node.id] = {
          cx: rect.left - viewportRect.left + rect.width / 2,
          cy: rect.top - viewportRect.top + rect.height / 2,
          width: rect.width,
          height: rect.height,
        };
      }
      setCanvasNodeGeometry(nextGeometry);
    }

    measureCanvasNodeCenters();

    const viewport = viewportRef.current;
    const resizeObserver = new ResizeObserver(() => {
      measureCanvasNodeCenters();
    });
    resizeObserver.observe(viewport);
    window.addEventListener("resize", measureCanvasNodeCenters);
    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("resize", measureCanvasNodeCenters);
    };
  }, [canvasHydrated, canvasNodes, canvasOffset, canvasScale]);

  function setActivePack(packId: string) {
    setSelectedPackId(packId);
    setAgentSession(null);
    setToolLogs([]);
    setErrorMessage(null);
    setSuccessMessage(null);
  }

  function updateEditorTab(tabId: string, updater: (draft: CardEditorDraft) => CardEditorDraft) {
    setEditorTabs((current) =>
      current.map((tab) => {
        if (tab.id !== tabId) {
          return tab;
        }
        const nextDraft = updater(tab.draft);
        return {
          ...tab,
          title: nextDraft.cardId || nextDraft.title || "New Card",
          draft: nextDraft,
        };
      }),
    );
  }

  function upsertEditorTab(tab: CardEditorTab) {
    setEditorTabs((current) => {
      const existingIndex = current.findIndex((entry) => entry.id === tab.id);
      if (existingIndex < 0) {
        return [...current, tab];
      }
      return current.map((entry) => (entry.id === tab.id ? tab : entry));
    });
  }

  function removeEditorTab(tabId: string) {
    setEditorTabs((current) => current.filter((tab) => tab.id !== tabId));
    setActiveTabId((current) => (current === tabId ? CANVAS_TAB_ID : current));
  }

  async function refreshCards() {
    if (!selectedPackId) {
      return;
    }
    setIsCardsLoading(true);
    try {
      const updated = await getDesignerCards(selectedPackId);
      setCards(updated);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to refresh cards.");
    } finally {
      setIsCardsLoading(false);
    }
  }

  async function openCardEditor(cardPath: string) {
    const existing = editorTabs.find((tab) => tab.draft.originalPath === cardPath);
    if (existing) {
      setActiveTabId(existing.id);
      return;
    }
    if (!selectedPackId) {
      return;
    }
    setIsBusy(true);
    setErrorMessage(null);
    try {
      const payload = await loadDesignerCard(selectedPackId, cardPath);
      const draft = buildInitialDraftFromPayload(payload);
      const tab: CardEditorTab = {
        id: payload.path,
        title: payload.card_id,
        draft: { ...draft, tabId: payload.path },
      };
      upsertEditorTab(tab);
      setActiveTabId(tab.id);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to load card.");
    } finally {
      setIsBusy(false);
    }
  }

  function openNewCardTab(fullFolderPath: string) {
    const { category, nestedFolder } = splitTreeFolder(fullFolderPath);
    const nextCardType = singularizeCategory(category || cardTypes[0] || "card");
    const tab = createBlankCardDraft({
      title: "New Card",
      cardType: nextCardType,
      folderPath: nestedFolder,
    });
    upsertEditorTab({
      id: tab.tabId,
      title: tab.title,
      draft: tab,
    });
    setActiveTabId(tab.tabId);
  }

  function handleCreateFolder(parentPath: string) {
    const folderName = window.prompt("New folder name");
    const normalizedName = normalizePath(folderName ?? "");
    if (!normalizedName) {
      return;
    }
    const nextPath = normalizePath(parentPath ? `${parentPath}/${normalizedName}` : normalizedName);
    setLocalFolders((current) => (current.includes(nextPath) ? current : [...current, nextPath]));
    setExpandedFolders((current) => ({ ...current, [parentPath]: true, [nextPath]: true }));
    setSuccessMessage(`Created local folder ${nextPath}.`);
  }

  function addCardToCanvas(card: DesignerCardSummary) {
    const existing = canvasNodes.find((node) => node.cardPath === card.path);
    if (existing) {
      setSelectedNodeId(existing.id);
      setActiveTabId(CANVAS_TAB_ID);
      return;
    }
    const viewport = viewportRef.current?.getBoundingClientRect();
    const baseX = viewport ? (viewport.width / 2 - canvasOffset.x) / canvasScale - 110 : 120;
    const baseY = viewport ? (viewport.height / 2 - canvasOffset.y) / canvasScale - 70 : 120;
    const nextIndex = canvasNodes.length;
    const col = nextIndex % 3;
    const row = Math.floor(nextIndex / 3);
    const gridOffsetX = col * 280;
    const gridOffsetY = row * 180;
    const node: CanvasNode = {
      id: `node-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      cardPath: card.path,
      title: card.title,
      cardType: card.card_type,
      x: baseX + gridOffsetX,
      y: baseY + gridOffsetY,
    };
    setCanvasNodes((current) => [...current, node]);
    setSelectedNodeId(node.id);
    setActiveTabId(CANVAS_TAB_ID);
  }

  function handleCanvasNodeClick(nodeId: string) {
    if (connectSourceId === CONNECT_PICK_SOURCE_ID) {
      setConnectSourceId(nodeId);
      setSelectedNodeId(nodeId);
      setSelectedEdgeId(null);
      return;
    }

    if (connectSourceId && connectSourceId !== nodeId) {
      const label = window.prompt("Connection label", "") ?? "";
      setCanvasEdges((current) => [
        ...current,
        ...(current.some((edge) => edge.fromId === connectSourceId && edge.toId === nodeId)
          ? []
          : [
              {
                id: `edge-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                fromId: connectSourceId,
                toId: nodeId,
                label: label.trim(),
              },
            ]),
      ]);
      setConnectSourceId(null);
      setSelectedEdgeId(null);
      return;
    }
    if (connectSourceId === nodeId) {
      setConnectSourceId(null);
    }
    setSelectedNodeId(nodeId);
    setSelectedEdgeId(null);
  }

  function handleCanvasNodeDragStart(node: CanvasNode, event: ReactMouseEvent<HTMLDivElement>) {
    event.stopPropagation();
    dragStateRef.current = {
      type: "node",
      nodeId: node.id,
      pointerX: event.clientX,
      pointerY: event.clientY,
      originX: node.x,
      originY: node.y,
    };
    setSelectedNodeId(node.id);
  }

  function handleCanvasPanStart(event: ReactMouseEvent<HTMLDivElement>) {
    const target = event.target as HTMLElement | null;
    if (target?.closest(".designer-canvas-node, .designer-edge-label")) {
      return;
    }
    dragStateRef.current = {
      type: "pan",
      pointerX: event.clientX,
      pointerY: event.clientY,
      originX: canvasOffset.x,
      originY: canvasOffset.y,
    };
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
    setConnectSourceId(null);
  }

  function handleCanvasWheel(event: ReactWheelEvent<HTMLDivElement>) {
    if (event.ctrlKey || event.metaKey) {
      event.preventDefault();
      const nextScale = Math.min(1.8, Math.max(0.5, canvasScale - event.deltaY * 0.001));
      setCanvasScale(Number(nextScale.toFixed(2)));
      return;
    }
    setCanvasOffset((current) => ({
      x: current.x - event.deltaX,
      y: current.y - event.deltaY,
    }));
  }

  function startConnection() {
    if (connectSourceId) {
      setConnectSourceId(null);
      return;
    }
    if (selectedNodeId) {
      setConnectSourceId(selectedNodeId);
      setSelectedEdgeId(null);
      return;
    }
    setConnectSourceId(CONNECT_PICK_SOURCE_ID);
    setErrorMessage("Click a source node, then click a target node to create a connection.");
    setSelectedEdgeId(null);
  }

  function removeSelectedCanvasItem() {
    if (selectedEdgeId) {
      setCanvasEdges((current) => current.filter((edge) => edge.id !== selectedEdgeId));
      setSelectedEdgeId(null);
      return;
    }
    if (selectedNodeId) {
      setCanvasNodes((current) => current.filter((node) => node.id !== selectedNodeId));
      setCanvasEdges((current) =>
        current.filter((edge) => edge.fromId !== selectedNodeId && edge.toId !== selectedNodeId),
      );
      if (connectSourceId === selectedNodeId) {
        setConnectSourceId(null);
      }
      setSelectedNodeId(null);
    }
  }

  function resetCanvasView() {
    setCanvasOffset({ x: 0, y: 0 });
    setCanvasScale(1);
  }

  async function handleGenerateTemplate() {
    if (!activeEditorTab || !selectedPackId) {
      return;
    }
    const draft = activeEditorTab.draft;
    setIsBusy(true);
    setErrorMessage(null);
    try {
      const template = await getDesignerCardTemplate(selectedPackId, draft.customCardType.trim() || draft.cardType);
      updateEditorTab(activeEditorTab.id, (current) => ({
        ...current,
        frontmatterText: stringifyFrontmatter(template),
      }));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to generate template.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleSaveCard() {
    if (!activeEditorTab || !selectedPackId) {
      return;
    }
    const draft = activeEditorTab.draft;
    const currentCardType = draft.customCardType.trim() || draft.cardType.trim() || "card";
    setIsBusy(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const payload = await saveDesignerCard(selectedPackId, {
        card_type: currentCardType,
        card_id: draft.cardId.trim(),
        folder_path: normalizePath(draft.folderPath) || undefined,
        frontmatter_text: draft.frontmatterText,
        body: draft.body,
        original_path: draft.originalPath || undefined,
      });
      const nextTabId = payload.path;
      const nextDraft = buildInitialDraftFromPayload(payload);
      setEditorTabs((current) =>
        current.map((tab) =>
          tab.id === activeEditorTab.id
            ? {
                id: nextTabId,
                title: payload.card_id,
                draft: { ...nextDraft, tabId: nextTabId },
              }
            : tab,
        ),
      );
      setCanvasNodes((current) =>
        current.map((node) =>
          node.cardPath === draft.originalPath || node.cardPath === payload.path
            ? {
                ...node,
                cardPath: payload.path,
                title: payload.card_id,
                cardType: payload.card_type,
              }
            : node,
        ),
      );
      setActiveTabId(nextTabId);
      await refreshCards();
      setSuccessMessage(`Saved ${payload.card_id} to ${formatFolderTarget(payload.card_type, payload.folder_path)}.`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save card.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleValidateCard() {
    if (!activeEditorTab) {
      return;
    }
    const draft = activeEditorTab.draft;
    setIsBusy(true);
    setErrorMessage(null);
    try {
      await validateDesignerCard({
        frontmatter_text: draft.frontmatterText,
        body: draft.body,
      });
      setSuccessMessage("Card validation passed.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Validation failed.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleDeleteCard() {
    if (!activeEditorTab || !activeEditorTab.draft.originalPath || !selectedPackId) {
      setErrorMessage("Load an existing card before deleting it.");
      return;
    }
    setIsBusy(true);
    setErrorMessage(null);
    try {
      const deletedNodeIds = canvasNodes
        .filter((node) => node.cardPath === activeEditorTab.draft.originalPath)
        .map((node) => node.id);
      await deleteDesignerCard(selectedPackId, activeEditorTab.draft.originalPath);
      setCanvasNodes((current) => current.filter((node) => node.cardPath !== activeEditorTab.draft.originalPath));
      setCanvasEdges((current) =>
        current.filter((edge) => !deletedNodeIds.includes(edge.fromId) && !deletedNodeIds.includes(edge.toId)),
      );
      removeEditorTab(activeEditorTab.id);
      await refreshCards();
      setSuccessMessage("Card deleted.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to delete card.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleCreatePack() {
    setIsBusy(true);
    setErrorMessage(null);
    try {
      const payload = await createDesignerPack(createPackDraft);
      const nextPacks = [...runtimePacks, { ...payload, cards_root: "cards", enabled: false, source: "local" }];
      setRuntimePacks(nextPacks);
      setCreatePackDraft(createEmptyPackDraft());
      setAgentSession(null);
      setToolLogs([]);
      setSelectedPackId(payload.pack_id);
      setActiveTabId(CANVAS_TAB_ID);
      setSuccessMessage(`Created pack ${payload.name}.`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to create pack.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleSendAgentMessage() {
    if (!agentSession || !agentInput.trim()) {
      return;
    }
    setIsBusy(true);
    setErrorMessage(null);
    try {
      const response = await sendDesignerAgentMessage(agentSession.session_id, agentInput.trim());
      setAgentSession((current) =>
        current
          ? {
              ...current,
              selected_pack_id: response.selected_pack_id,
              state: response.state,
            }
          : null,
      );
      setToolLogs(response.tool_logs);
      setAgentInput("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to send message to agent.");
    } finally {
      setIsBusy(false);
    }
  }

  const renderedTabs = [
    { id: CANVAS_TAB_ID, label: "Canvas", closable: false },
    ...editorTabs.map((tab) => ({ id: tab.id, label: tab.title || "Card", closable: true })),
    { id: CREATE_PACK_TAB_ID, label: "New Pack", closable: false },
  ];

  function renderFolder(folder: TreeFolder) {
    if (!visibleFolderPaths.has(folder.path)) {
      return null;
    }
    const isExpanded = expandedFolders[folder.path] ?? folder.depth < 1;
    const childFolders = folderChildren.get(folder.path) ?? [];
    const childCards = (cardsByFolder.get(folder.path) ?? []).filter((card) => {
      if (!keywordLower) {
        return true;
      }
      const haystack = [card.title, card.card_id, card.path, card.card_type].join(" ").toLowerCase();
      return haystack.includes(keywordLower);
    });
    return (
      <div className="designer-tree-node" key={folder.path}>
        <div className="designer-tree-row">
          <button
            className="designer-tree-label folder"
            onClick={() => setExpandedFolders((current) => ({ ...current, [folder.path]: !isExpanded }))}
            type="button"
          >
            <span className="designer-tree-caret">{isExpanded ? "▾" : "▸"}</span>
            <span>{folder.name}</span>
          </button>
          <div className="designer-tree-actions">
            <button onClick={() => openNewCardTab(folder.path)} type="button">
              New Card
            </button>
            <button onClick={() => handleCreateFolder(folder.path)} type="button">
              New Folder
            </button>
          </div>
        </div>
        {isExpanded ? (
          <div className="designer-tree-children">
            {childFolders.map((child) => renderFolder(child))}
            {childCards.map((card) => (
              <div className="designer-tree-card-row" key={card.path}>
                <div className="designer-tree-card-copy">
                  <div className="designer-tree-card-title">{card.title}</div>
                  <div className="designer-tree-card-meta">
                    {card.card_type} · {card.path}
                  </div>
                </div>
                <div className="designer-tree-actions">
                  <button onClick={() => addCardToCanvas(card)} type="button">
                    Add
                  </button>
                  <button onClick={() => void openCardEditor(card.path)} type="button">
                    Edit
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    );
  }

  function renderCanvas() {
    const nodeLookup = new Map(canvasNodes.map((node) => [node.id, node]));
    return (
      <section className="designer-workspace-panel">
        <div className="designer-workspace-toolbar">
          <div className="designer-toolbar-group">
            <button
              className={`designer-toolbar-button ${connectSourceId ? "active" : ""}`}
              onClick={startConnection}
              type="button"
            >
              {connectSourceId === CONNECT_PICK_SOURCE_ID
                ? "Pick source node"
                : connectSourceId
                  ? "Pick target node"
                  : "Connect"}
            </button>
            <button className="designer-toolbar-button" onClick={removeSelectedCanvasItem} type="button">
              Remove Selected
            </button>
          </div>
          <div className="designer-toolbar-group">
            <button className="designer-toolbar-button" onClick={resetCanvasView} type="button">
              Reset View
            </button>
            <button
              className="designer-toolbar-button"
              onClick={() => {
                setCanvasNodes([]);
                setCanvasEdges([]);
              }}
              type="button"
            >
              Clear Nodes
            </button>
          </div>
        </div>

        <div className="designer-infinite-viewport" onMouseDown={handleCanvasPanStart} onWheel={handleCanvasWheel} ref={viewportRef}>
          <div
            className="designer-infinite-surface"
            style={{
              backgroundPosition: `${canvasOffset.x}px ${canvasOffset.y}px`,
              backgroundSize: `${28 * canvasScale}px ${28 * canvasScale}px`,
            }}
          >
            <svg className="designer-canvas-svg">
              <defs>
                <marker
                  id="designer-edge-arrow"
                  markerWidth="10"
                  markerHeight="10"
                  refX="8"
                  refY="3"
                  orient="auto"
                  markerUnits="strokeWidth"
                >
                  <path d="M0,0 L0,6 L9,3 z" fill="#ff2d55" />
                </marker>
              </defs>
              {canvasEdges.map((edge) => {
                const fromNode = nodeLookup.get(edge.fromId);
                const toNode = nodeLookup.get(edge.toId);
                if (!fromNode || !toNode) {
                  return null;
                }
                const fromNodeGeometry = canvasNodeGeometry[fromNode.id] ?? canvasNodeFallbackGeometry(fromNode, canvasOffset, canvasScale);
                const toNodeGeometry = canvasNodeGeometry[toNode.id] ?? canvasNodeFallbackGeometry(toNode, canvasOffset, canvasScale);
                const fromPoint = getRectangleAnchorPoint(fromNodeGeometry, toNodeGeometry);
                const toPoint = getRectangleAnchorPoint(toNodeGeometry, fromNodeGeometry);
                const fromX = fromPoint.x;
                const fromY = fromPoint.y;
                const toX = toPoint.x;
                const toY = toPoint.y;
                const midX = (fromX + toX) / 2;
                const midY = (fromY + toY) / 2;
                return (
                  <g key={edge.id}>
                    <line
                      className={selectedEdgeId === edge.id ? "selected" : ""}
                      markerEnd="url(#designer-edge-arrow)"
                      onClick={() => {
                        setSelectedEdgeId(edge.id);
                        setSelectedNodeId(null);
                      }}
                      x1={fromX}
                      x2={toX}
                      y1={fromY}
                      y2={toY}
                    />
                    <foreignObject height="28" width="120" x={midX - 60} y={midY - 14}>
                      <button
                        className={`designer-edge-label ${selectedEdgeId === edge.id ? "active" : ""}`}
                        onClick={() => {
                          const nextLabel = window.prompt("Connection label", edge.label) ?? edge.label;
                          setCanvasEdges((current) =>
                            current.map((item) => (item.id === edge.id ? { ...item, label: nextLabel.trim() } : item)),
                          );
                          setSelectedEdgeId(edge.id);
                        }}
                        type="button"
                      >
                        {edge.label || "label"}
                      </button>
                    </foreignObject>
                  </g>
                );
              })}
            </svg>

            {canvasNodes.map((node) => (
              <button
                className={`designer-canvas-node ${selectedNodeId === node.id ? "selected" : ""} ${connectSourceId === node.id ? "source" : ""}`}
                key={node.id}
                ref={(element) => {
                  canvasNodeRefs.current[node.id] = element;
                }}
                onClick={() => handleCanvasNodeClick(node.id)}
                onDoubleClick={() => void openCardEditor(node.cardPath)}
                style={{
                  transform: `translate(${node.x * canvasScale + canvasOffset.x}px, ${node.y * canvasScale + canvasOffset.y}px) scale(${canvasScale})`,
                  transformOrigin: "top left",
                }}
                type="button"
              >
                <div className="designer-canvas-node-grip" onMouseDown={(event) => handleCanvasNodeDragStart(node, event)}>
                  Drag
                </div>
                <div className="designer-canvas-node-type">{node.cardType}</div>
                <div className="designer-canvas-node-title">{node.title}</div>
                <div className="designer-canvas-node-path">{node.cardPath}</div>
              </button>
            ))}

            <div className="designer-canvas-hint">
              Infinite canvas: drag background to pan, use Ctrl/Command + wheel to zoom, double click a card node to open its editor.
            </div>
          </div>
        </div>
      </section>
    );
  }

  function renderEditor() {
    if (!activeEditorTab) {
      return (
        <section className="designer-workspace-panel empty">
          <div className="designer-empty-state">
            Pick a card from the file tree, or click New Card on a folder to open an editor tab here.
          </div>
        </section>
      );
    }
    const draft = activeEditorTab.draft;
    const currentCardType = draft.customCardType.trim() || draft.cardType.trim() || "card";
    return (
      <section className="designer-workspace-panel">
        <div className="designer-editor-header">
          <div>
            <h2>{draft.cardId || "New Card"}</h2>
            <p>Canvas stays pinned; editor tabs can be opened and closed as needed.</p>
          </div>
          <div className="designer-inline-actions">
            <button onClick={() => void handleGenerateTemplate()} type="button">
              Generate Template
            </button>
            <button onClick={() => void handleValidateCard()} type="button">
              Validate
            </button>
            <button disabled={!draft.originalPath} onClick={() => void handleDeleteCard()} type="button">
              Delete
            </button>
            <button className="primary" onClick={() => void handleSaveCard()} type="button">
              Save
            </button>
          </div>
        </div>

        <div className="designer-editor-grid">
          <label className="designer-field">
            <span>Type</span>
            <select
              onChange={(event) =>
                updateEditorTab(activeEditorTab.id, (current) => ({ ...current, cardType: event.target.value }))
              }
              value={draft.cardType}
            >
              {cardTypes.map((cardType) => (
                <option key={cardType} value={cardType}>
                  {cardType}
                </option>
              ))}
            </select>
          </label>

          <label className="designer-field">
            <span>Custom Type</span>
            <input
              onChange={(event) =>
                updateEditorTab(activeEditorTab.id, (current) => ({ ...current, customCardType: event.target.value }))
              }
              placeholder="Optional type override"
              value={draft.customCardType}
            />
          </label>

          <label className="designer-field">
            <span>Card ID</span>
            <input
              onChange={(event) =>
                updateEditorTab(activeEditorTab.id, (current) => ({ ...current, cardId: event.target.value, title: event.target.value || "New Card" }))
              }
              placeholder="card_id"
              value={draft.cardId}
            />
          </label>

          <label className="designer-field">
            <span>Nested Folder</span>
            <input
              onChange={(event) =>
                updateEditorTab(activeEditorTab.id, (current) => ({ ...current, folderPath: event.target.value }))
              }
              placeholder="chapter_02/scene_01"
              value={draft.folderPath}
            />
          </label>
        </div>

        <div className="designer-field helper">
          <span>Target Folder</span>
          <div className="designer-helper-copy">{formatFolderTarget(currentCardType, draft.folderPath)}</div>
        </div>

        <label className="designer-field stacked">
          <span>Frontmatter (JSON)</span>
          <textarea
            onChange={(event) =>
              updateEditorTab(activeEditorTab.id, (current) => ({ ...current, frontmatterText: event.target.value }))
            }
            value={draft.frontmatterText}
          />
        </label>

        <label className="designer-field stacked grow">
          <span>Body (Markdown)</span>
          <textarea
            className="body"
            onChange={(event) =>
              updateEditorTab(activeEditorTab.id, (current) => ({ ...current, body: event.target.value }))
            }
            value={draft.body}
          />
        </label>
      </section>
    );
  }

  function renderCreatePack() {
    return (
      <section className="designer-workspace-panel">
        <div className="designer-editor-header">
          <div>
            <h2>Create Pack</h2>
            <p>Create a new pack, then continue working in the file tree and canvas view.</p>
          </div>
          <div className="designer-inline-actions">
            <button className="primary" onClick={() => void handleCreatePack()} type="button">
              Save Pack
            </button>
          </div>
        </div>

        <div className="designer-editor-grid">
          {(["pack_id", "name", "version", "author"] as const).map((field) => (
            <label className="designer-field" key={field}>
              <span>{field}</span>
              <input
                onChange={(event) => setCreatePackDraft((current) => ({ ...current, [field]: event.target.value }))}
                value={createPackDraft[field]}
              />
            </label>
          ))}
        </div>

        <label className="designer-field stacked grow">
          <span>Description</span>
          <textarea
            className="body"
            onChange={(event) => setCreatePackDraft((current) => ({ ...current, description: event.target.value }))}
            value={createPackDraft.description}
          />
        </label>
      </section>
    );
  }

  return (
    <main className="light-app-shell designer-page-shell">
      <div className="light-app-frame designer-page-frame">
        <AppSidebar activePath="/card-designer" currentUser={currentUser} />

        <section className="light-main designer-v2-shell">
          <header className="designer-v2-topbar">
            <div>
              <h1 className="light-page-title">Card Designer</h1>
              <p className="designer-v2-subtitle">File tree on the left, infinite canvas in the center, pack build agent on the right.</p>
            </div>

            <div className="designer-v2-topbar-actions">
              <select
                className="designer-topbar-select"
                disabled={runtimePacks.length === 0}
                onChange={(event) => setActivePack(event.target.value)}
                value={selectedPackId}
              >
                {runtimePacks.length === 0 ? (
                  <option value="">No packs yet</option>
                ) : (
                  runtimePacks.map((pack) => (
                    <option key={pack.pack_id} value={pack.pack_id}>
                      {pack.name} ({pack.pack_id})
                    </option>
                  ))
                )}
              </select>
              <button className="designer-topbar-button" onClick={() => setActiveTabId(CREATE_PACK_TAB_ID)} type="button">
                Create Pack
              </button>
              <button className="designer-topbar-button" onClick={() => setActiveTabId(CANVAS_TAB_ID)} type="button">
                Open Canvas
              </button>
            </div>
          </header>

          <div className="designer-v2-grid">
            <section className="light-card designer-v2-panel designer-tree-panel">
              <div className="designer-panel-head">
                <div>
                  <h2>File Structure</h2>
                  <p>Folders can spawn cards or child folders. Cards can be added to the canvas or opened in an editor tab.</p>
                </div>
                <button className="designer-minor-button" onClick={() => handleCreateFolder("")} type="button">
                  Root Folder
                </button>
              </div>

              <input
                className="designer-tree-search"
                onChange={(event) => setKeyword(event.target.value)}
                placeholder="Filter folders and cards"
                value={keyword}
              />

              <div className="designer-tree-meta">
                {isCardsLoading ? "Loading pack files..." : `${folderList.length} folders · ${cards.length} cards`}
              </div>

              <div className="designer-tree-scroll">
                {(folderChildren.get("") ?? []).map((folder) => renderFolder(folder))}
                {folderList.length === 0 && !isCardsLoading ? (
                  <div className="designer-empty-state">Create a pack or add cards to start building the tree.</div>
                ) : null}
              </div>
            </section>

            <section className="light-card designer-v2-panel designer-workspace-shell">
              <div className="designer-workspace-tabs">
                {renderedTabs.map((tab) => (
                  <div className={`designer-workspace-tab ${activeTabId === tab.id ? "active" : ""}`} key={tab.id}>
                    <button onClick={() => setActiveTabId(tab.id)} type="button">
                      {tab.label}
                    </button>
                    {tab.closable ? (
                      <button className="close" onClick={() => removeEditorTab(tab.id)} type="button">
                        x
                      </button>
                    ) : null}
                  </div>
                ))}
              </div>

              <div className="designer-workspace-body">
                {activeTabId === CANVAS_TAB_ID ? renderCanvas() : null}
                {activeTabId === CREATE_PACK_TAB_ID ? renderCreatePack() : null}
                {activeTabId !== CANVAS_TAB_ID && activeTabId !== CREATE_PACK_TAB_ID ? renderEditor() : null}
              </div>
            </section>

            <section className="light-card designer-v2-panel designer-agent-panel-v2">
              <div className="designer-panel-head">
                <div>
                  <h2>Pack Build Agent</h2>
                  <p>Keep the agent visible while editing or arranging the graph.</p>
                </div>
                <div className="designer-agent-target">
                  <span>Write Target</span>
                  <strong>{agentTargetPackId || "(none)"}</strong>
                  <small>{agentTargetPackName}</small>
                </div>
              </div>

              <div className="designer-agent-history-v2">
                {agentHistory.length === 0 ? (
                  <div className="designer-empty-state">No designer chat yet. Ask the agent to plan card batches, fill missing event links, or draft content.</div>
                ) : (
                  agentHistory.map((entry, index) => {
                    const role =
                      typeof entry === "object" && entry && "role" in entry
                        ? String((entry as { role?: unknown }).role ?? "assistant")
                        : "assistant";
                    const content =
                      typeof entry === "object" && entry && "content" in entry
                        ? String((entry as { content?: unknown }).content ?? "")
                        : "";
                    const preview = role === "assistant" ? parsePendingBatchSavePreview(content) : null;
                    return (
                      <div className={`designer-chat-row-v2 ${role === "user" ? "user" : "assistant"}`} key={`${role}-${index}`}>
                        <div className="designer-chat-role-v2">{role.toUpperCase()}</div>
                        {!preview ? (
                          <div className="designer-chat-content-v2">{content}</div>
                        ) : (
                          <div className="designer-pending-plan-v2">
                            <div className="designer-pending-plan-head-v2">
                              Pending write: {preview.pack_id || "(unknown)"} · {preview.cards.length} cards
                            </div>
                            {preview.cards.map((card) => (
                              <div className="designer-pending-card-v2" key={`${card.card_type}-${card.card_id}`}>
                                <strong>
                                  {card.title} ({card.card_type})
                                </strong>
                                <span>{card.card_id}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>

              <label className="designer-field stacked">
                <span>Designer Prompt</span>
                <textarea
                  className="designer-agent-input-v2"
                  onChange={(event) => setAgentInput(event.target.value)}
                  placeholder="Describe missing event cards, card relationships, or edits you want the agent to draft."
                  value={agentInput}
                />
              </label>

              <button
                className="designer-send-button"
                disabled={isBusy || !agentSession || !agentInput.trim()}
                onClick={() => void handleSendAgentMessage()}
                type="button"
              >
                {isBusy ? "Working..." : "Send To Agent"}
              </button>

              {toolLogs.length > 0 ? (
                <div className="designer-tool-log-v2">
                  {toolLogs.map((line) => (
                    <div key={line}>{line}</div>
                  ))}
                </div>
              ) : null}
            </section>
          </div>

          {errorMessage ? <div className="light-error-banner">{errorMessage}</div> : null}
          {successMessage ? <div className="light-success-banner">{successMessage}</div> : null}
        </section>
      </div>
    </main>
  );
}
