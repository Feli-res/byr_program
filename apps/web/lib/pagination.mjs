// Page-number window shared by every paginated list.
// Returns numbers plus the string "ellipsis" between gaps.
export function pageWindow(current, totalPages, span = 2) {
  const total = Math.max(1, Math.floor(Number(totalPages) || 1));
  const page = Math.min(Math.max(1, Math.floor(Number(current) || 1)), total);
  if (total <= 7) return Array.from({length: total}, (_, index) => index + 1);
  const selected = new Set([1, total, page]);
  for (let value = Math.max(2, page - span); value <= Math.min(total - 1, page + span); value += 1) {
    selected.add(value);
  }
  const result = [];
  let previous = 0;
  for (const value of [...selected].sort((a, b) => a - b)) {
    if (value - previous > 1) result.push('ellipsis');
    result.push(value);
    previous = value;
  }
  return result;
}
