import { create } from "zustand";

export type Item = {
    Id: string;
    CreatedAt: string;
};

type StoreState = {
    items: Item[];
    indexById: Record<string, number>;

    setMany: (items: Item[]) => void;
    upsertItem: (a: Item) => void;
    applyPatch: (id: string, patch: Partial<Item>) => void;

    getById: (id: string) => Item | undefined;
};

function buildIndex(items: Item[]): Record<string, number> {
    const idx: Record<string, number> = {};

    for (let i = 0; i < items.length; i++) idx[items[i].Id] = i;

    return idx;
}

export const useAnalysisDataStore = create<StoreState>((set, get) => ({
    items: [],
    indexById: {},

    setMany: (items) =>
        set(() => ({
            items: items,
            indexById: buildIndex(items),
        })),

    upsertItem: (a) =>
        set((state) => {
            const existingIndex = state.indexById[a.Id];

            // Remove existing item if present
            let items =
                existingIndex === undefined
                    ? state.items.slice()
                    : state.items.filter((_, i) => i !== existingIndex);

            // Find insertion index based on CreatedAt (newest first)
            const insertAt = items.findIndex(
                (item) => new Date(a.CreatedAt).getTime() > new Date(item.CreatedAt).getTime()
            );

            if (insertAt === -1) items.push(a);
            else items.splice(insertAt, 0, a);

            return {items, indexById: buildIndex(items)};
        }),

    applyPatch: (id, patch) =>
        set((state) => {
            const existingIndex = state.indexById[id];

            // If the item does not exist yet, create it from the patch
            const updatedItem: Item =
                existingIndex === undefined
                    ? ({ Id: id, ...patch } as Item)
                    : ({ ...state.items[existingIndex], ...patch } as Item);

            // Remove old version if present
            let items =
                existingIndex === undefined
                    ? state.items.slice()
                    : state.items.filter((_, i) => i !== existingIndex);

            // Insert based on CreatedAt (newest first)
            const updatedTs = new Date(updatedItem.CreatedAt).getTime();
            const insertAt = items.findIndex(
                (item) => updatedTs > new Date(item.CreatedAt).getTime()
            );

            if (insertAt === -1) items.push(updatedItem);
            else items.splice(insertAt, 0, updatedItem);

            return {items, indexById: buildIndex(items)};
        }),

    getById: (id) => {
        const { items, indexById } = get();
        const i = indexById[id];
        return i === undefined ? undefined : items[i];
    },
}));