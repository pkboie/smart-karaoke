export const RESULT_KEY = "smart-karaoke:last-result";

export function singingLink(songId, settings = {}) {
  const params = new URLSearchParams({ song: songId, ...settings });
  return `./sing.html?${params}`;
}
