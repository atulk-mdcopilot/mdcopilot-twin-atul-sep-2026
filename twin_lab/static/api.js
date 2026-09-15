// One local JSON transport shared by capture and planning screens.
/** @param {string} path @param {unknown} [body] @returns {Promise<any>} */
export async function request(path, body) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    /** @type {RequestInit} */
    const options = {signal: controller.signal, cache: "no-store", credentials: "same-origin"};
    if (body !== undefined) Object.assign(options, {method: "POST", headers: {"Content-Type": "application/json", "X-Twin-Lab": "1"}, body: JSON.stringify(body)});
    const result = await fetch(path, options);
    const data = await result.json();
    if (!result.ok) {
      const error = Object.assign(new Error(data.error || `Request failed (${result.status}).`), {status: result.status});
      throw error;
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The local server did not respond in time.");
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

/** @param {unknown} data @param {string} filename */
export function downloadJSON(data, filename) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: "application/json"}));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
