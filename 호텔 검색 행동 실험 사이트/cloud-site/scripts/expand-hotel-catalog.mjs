import { readFile, writeFile } from "node:fs/promises";

const file = new URL("../app/hotel-data.ts", import.meta.url);
const cities = {
  Tokyo: [35.45, 139.35, 35.9, 140.05],
  Osaka: [34.5, 135.3, 34.9, 135.75],
  Kyoto: [34.88, 135.62, 35.14, 135.9],
  Fukuoka: [33.48, 130.28, 33.72, 130.55],
  Sapporo: [43.0, 141.25, 43.13, 141.46],
};

const original = await readFile(file, "utf8");
const cacheFile = new URL("./hotel-catalog-cache.json", import.meta.url);
let cache = {};
try {
  cache = JSON.parse(await readFile(cacheFile, "utf8"));
} catch {}
const existing = {};
for (const city of Object.keys(cities)) {
  const match = original.match(new RegExp(`  ${city}: \\[([\\s\\S]*?)\\n  \\](?:,|\\n)`));
  if (!match) throw new Error(`Could not read existing ${city} catalog`);
  existing[city] = [...match[1].matchAll(/"((?:[^"\\]|\\.)*)"/g)].map((m) =>
    JSON.parse(`"${m[1]}"`),
  );
}

const next = {};
const endpoints = [
  "https://overpass-api.de/api/interpreter",
  "https://overpass.private.coffee/api/interpreter",
  "https://overpass.kumi.systems/api/interpreter",
  "https://overpass.nchc.org.tw/api/interpreter",
];
for (const [city, bbox] of Object.entries(cities)) {
  if (cache[city]?.length >= 150) {
    next[city] = cache[city];
    console.log(`${city}: ${next[city].length} (cached)`);
    continue;
  }
  const query = `[out:json][timeout:90];nwr["tourism"~"^(hotel|hostel|guest_house|motel|ryokan)$"]["name"](${bbox.join(",")});out tags 2500;`;
  let response;
  for (const endpoint of endpoints) {
    try {
      response = await fetch(`${endpoint}?data=${encodeURIComponent(query)}`, {
        headers: { "User-Agent": "StayTraceResearch/1.0" },
        signal: AbortSignal.timeout(45000),
      });
    } catch {
      response = undefined;
    }
    if (response?.ok) break;
    await new Promise((resolve) => setTimeout(resolve, 3000));
  }
  if (!response?.ok) throw new Error(`${city}: Overpass ${response?.status}`);
  const data = await response.json();
  const candidates = data.elements
    .map((item) => item.tags?.["name:en"] || item.tags?.name)
    .filter((name) => typeof name === "string" && name.trim().length >= 2)
    .map((name) => name.trim())
    .sort((a, b) => a.localeCompare(b, "en"));
  const seen = new Set();
  next[city] = [...existing[city], ...candidates].filter((name) => {
    const key = name.toLocaleLowerCase().replace(/\s+/g, " ");
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).slice(0, 200);
  if (next[city].length !== 200)
    throw new Error(`${city}: only ${next[city].length} unique properties`);
  cache[city] = next[city];
  await writeFile(cacheFile, JSON.stringify(cache, null, 2), "utf8");
  console.log(`${city}: ${next[city].length}`);
}

const lines = [
  "// Hotel names and city membership combine the previous tourism-directory catalog",
  "// with named OpenStreetMap accommodation records retrieved on 2026-08-27.",
  "// Rates, ratings, reviews, room features, availability, and inventory are simulations.",
  "export const REAL_HOTELS: Record<string, string[]> = {",
];
for (const [city, names] of Object.entries(next)) {
  lines.push(`  ${city}: [`);
  for (const name of names) lines.push(`    ${JSON.stringify(name)},`);
  lines.push("  ],");
}
lines.push("};", "");
await writeFile(file, lines.join("\n"), "utf8");
