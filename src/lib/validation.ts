export const MAX_FILE_BYTES = 25 * 1024 * 1024;
export const FILE_ACCEPT = ".pdf,.docx,.xlsx,.jpg,.jpeg,.png";
export function workspaceNameError(name: string, workspaces: { name: string }[]) {
  const value = name.trim();
  if (!value) return "Enter a workspace name.";
  if (workspaces.some((w) => w.name.trim().toLowerCase() === value.toLowerCase()))
    return "A workspace with this name already exists.";
  return null;
}
export function uploadError(file: { name: string; size: number }) {
  if (file.size > MAX_FILE_BYTES) return "Files must be 25 MB or smaller.";
  const ext = file.name.split(".").pop()?.toLowerCase();
  if (!ext || !FILE_ACCEPT.split(",").includes(`.${ext}`))
    return "Choose a PDF, Word file, spreadsheet, JPG or PNG.";
  return null;
}
