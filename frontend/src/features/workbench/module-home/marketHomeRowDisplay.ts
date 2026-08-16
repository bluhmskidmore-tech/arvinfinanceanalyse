import type { ModuleHomeDetailRow } from "./moduleHomeModel";

export function rowDisplayValue(row: ModuleHomeDetailRow): string {
  if (row.detail?.trim()) {
    return row.value;
  }
  const splitIndex = row.value.lastIndexOf("·");
  if (splitIndex > 0) {
    return row.value.slice(0, splitIndex).trim();
  }
  return row.value;
}

export function rowChangeText(row: ModuleHomeDetailRow): string | undefined {
  if (row.detail?.trim()) {
    return row.detail;
  }
  const splitIndex = row.value.lastIndexOf("·");
  if (splitIndex > 0) {
    const tail = row.value.slice(splitIndex + 1).trim();
    return tail || undefined;
  }
  return undefined;
}
