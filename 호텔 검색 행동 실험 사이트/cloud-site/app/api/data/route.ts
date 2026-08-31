import { env } from "cloudflare:workers";
import { NextRequest, NextResponse } from "next/server";
import { HOTEL_SUBREGIONS, REAL_HOTELS } from "../../hotel-data";
import { SUPPLIER_HOTEL_BY_NAME } from "../../hotel-supplier-data";
const idPrefixes: Record<string, string> = { USR: "U", SES: "S", SRC: "Q", EVT: "E", RSV: "B" };
const shortToken = (length = 9) => {
  const alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
  return Array.from(crypto.getRandomValues(new Uint8Array(length)),
    (byte) => alphabet[byte % alphabet.length]).join("");
};
const id = (prefix: string) => `${idPrefixes[prefix] || prefix[0]}${shortToken()}`;
const KST_OFFSET_MS = 9 * 60 * 60 * 1000;
const now = () =>
  new Date(Date.now() + KST_OFFSET_MS)
    .toISOString()
    .replace(/\.\d{3}Z$/, "+09:00");
const koreanDateTime = (value: unknown) => {
  if (!value) return "";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return String(value);
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Seoul",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(date)
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, part.value]),
  );
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second} KST`;
};
const tables = [
  `CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,name TEXT NOT NULL,created_at TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,started_at TEXT NOT NULL,ended_at TEXT)`,
  `CREATE TABLE IF NOT EXISTS hotels(id TEXT PRIMARY KEY,name TEXT NOT NULL,city TEXT NOT NULL,type TEXT NOT NULL,grade INTEGER NOT NULL,rating REAL NOT NULL,price INTEGER NOT NULL,reviews INTEGER NOT NULL,station_distance INTEGER NOT NULL,amenities TEXT NOT NULL,free_cancellation INTEGER NOT NULL,pay_at_hotel INTEGER NOT NULL,breakfast INTEGER NOT NULL,family_room INTEGER NOT NULL,pet_friendly INTEGER NOT NULL,pool INTEGER NOT NULL,spa INTEGER NOT NULL,chain TEXT,balcony INTEGER NOT NULL DEFAULT 0)`,
  `CREATE TABLE IF NOT EXISTS searches(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,session_id TEXT NOT NULL,parent_id TEXT,created_at TEXT NOT NULL,conditions TEXT NOT NULL,result_count INTEGER NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,session_id TEXT NOT NULL,search_id TEXT,hotel_id TEXT,name TEXT NOT NULL,page TEXT NOT NULL,properties TEXT NOT NULL,created_at TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS reservations(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,session_id TEXT NOT NULL,search_id TEXT NOT NULL,hotel_id TEXT NOT NULL,total_price INTEGER NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS room_inventory(id TEXT PRIMARY KEY,hotel_id TEXT NOT NULL,name TEXT NOT NULL,bed_type TEXT NOT NULL,view_type TEXT NOT NULL,size_sqm INTEGER NOT NULL,capacity INTEGER NOT NULL,breakfast INTEGER NOT NULL,free_cancellation INTEGER NOT NULL,pay_at_hotel INTEGER NOT NULL,spa_access INTEGER NOT NULL,bathtub INTEGER NOT NULL,smoking INTEGER NOT NULL,units_left INTEGER NOT NULL,price_modifier INTEGER NOT NULL,pool_access INTEGER NOT NULL DEFAULT 0,pet_friendly INTEGER NOT NULL DEFAULT 0,balcony INTEGER NOT NULL DEFAULT 0)`,
  `CREATE TABLE IF NOT EXISTS admin_deleted_rows(table_name TEXT NOT NULL,row_id TEXT NOT NULL,snapshot TEXT NOT NULL,deleted_at TEXT NOT NULL,deleted_by TEXT NOT NULL,owner_user_id TEXT NOT NULL DEFAULT '',PRIMARY KEY(table_name,row_id))`,
  `CREATE TABLE IF NOT EXISTS participant_identities(normalized_name TEXT PRIMARY KEY,user_id TEXT NOT NULL UNIQUE,display_name TEXT NOT NULL,created_at TEXT NOT NULL)`,
];
async function init() {
  await env.DB.batch(tables.map((s) => env.DB.prepare(s)));
  for (const statement of [
    "ALTER TABLE hotels ADD COLUMN balcony INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE room_inventory ADD COLUMN pool_access INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE room_inventory ADD COLUMN pet_friendly INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE room_inventory ADD COLUMN balcony INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE admin_deleted_rows ADD COLUMN owner_user_id TEXT NOT NULL DEFAULT ''",
  ]) {
    try {
      await env.DB.prepare(statement).run();
    } catch {
      // The hosted migration may already have added the column.
    }
  }
  const hn = await env.DB.prepare("SELECT COUNT(*) n FROM hotels").first<{
    n: number;
  }>();
  if ((hn?.n || 0) < 150) {
    const cs = ["Tokyo", "Osaka", "Kyoto", "Fukuoka", "Sapporo"],
      ts = ["Hotel", "Ryokan", "Resort", "Apartment", "Hostel", "Guesthouse"],
      chains = [
        null,
        "Sakura Stay",
        "Nippon Grand",
        "Urban Nest",
        "Hoshi Resorts",
      ],
      ws = ["Garden", "Central", "Harbor", "Sky", "Sakura", "Grand"],
      q = [];
    for (let i = 0; i < 180; i++) {
      const c = cs[i % 5],
        a = [
          "무료 Wi-Fi",
          ...(i % 2 === 0 ? ["조식"] : []),
          ...(i % 3 === 0 ? ["주차"] : []),
          ...(i % 5 === 0 ? ["수영장"] : []),
          ...(i % 6 === 0 ? ["스파"] : []),
        ];
      q.push(
        env.DB.prepare(
          "INSERT OR IGNORE INTO hotels VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ).bind(
          `H${String(i + 1).padStart(4, "0")}`,
          `${c} ${ws[i % 6]} ${i + 1}`,
          c,
          ts[i % 6],
          2 + (i % 4),
          6.5 + (i % 33) / 10,
          45000 + (i % 54) * 5000,
          15 + ((i * 97) % 3200),
          80 + ((i * 73) % 1500),
          JSON.stringify(a),
          i % 3 ? 1 : 0,
          i % 4 ? 1 : 0,
          i % 2 ? 0 : 1,
          i % 3 ? 0 : 1,
          i % 7 ? 0 : 1,
          i % 5 ? 0 : 1,
          i % 6 ? 0 : 1,
          chains[i % 5],
        ),
      );
    }
    for (let i = 0; i < q.length; i += 90)
      await env.DB.batch(q.slice(i, i + 90));
  }
  const rn = await env.DB.prepare(
    "SELECT COUNT(*) n FROM room_inventory",
  ).first<{ n: number }>();
  if ((rn?.n || 0) < 540) {
    const q = [];
    for (let i = 0; i < 180; i++)
      for (let r = 0; r < 3; r++)
        q.push(
          env.DB.prepare(
            "INSERT OR IGNORE INTO room_inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
          ).bind(
            `R${String(i + 1).padStart(4, "0")}_${r + 1}`,
            `H${String(i + 1).padStart(4, "0")}`,
            ["스탠다드 더블", "디럭스 트윈", "프리미엄 스위트"][r],
            ["퀸베드 1개", "싱글베드 2개", "킹베드 1개"][r],
            ["시티뷰", "가든뷰", "파노라마뷰"][r],
            24 + r * 9,
            2 + r,
            (i + r) % 2 ? 0 : 1,
            (i + r) % 3 ? 1 : 0,
            (i + r) % 4 ? 1 : 0,
            (i + r) % 2 ? 1 : 0,
            (i + r) % 3 ? 0 : 1,
            r === 0 ? 1 : 0,
            1 + ((i + r) % 4),
            r * 25000,
          ),
        );
    for (let i = 0; i < q.length; i += 90)
      await env.DB.batch(q.slice(i, i + 90));
  }
  await syncRealHotelCatalog();
}

async function syncRealHotelCatalog() {
  const current = await env.DB.prepare(
    "SELECT name FROM hotels WHERE id='H0001'",
  ).first<{ name: string }>();
  const total = await env.DB.prepare("SELECT COUNT(*) n FROM hotels").first<{
    n: number;
  }>();
  const catalogTail = await env.DB.prepare(
    "SELECT name FROM hotels WHERE id='H1000'",
  ).first<{ name: string }>();
  if (
    current?.name === REAL_HOTELS.Tokyo[0] &&
    catalogTail?.name === REAL_HOTELS.Sapporo[199] &&
    (total?.n || 0) >= 1000
  )
    return;

  const hotelWrites = [];
  const roomWrites = [];
  let i = 0;
  for (const [city, names] of Object.entries(REAL_HOTELS)) {
    for (const name of names.slice(0, 200)) {
      const hotelId = `H${String(i + 1).padStart(4, "0")}`;
      const amenities = [
        "무료 Wi-Fi",
        ...(i % 2 === 0 ? ["조식"] : []),
        ...(i % 5 === 0 ? ["수영장"] : []),
        ...(i % 6 === 0 ? ["스파"] : []),
        ...(i % 4 === 0 ? ["발코니"] : []),
      ];
      hotelWrites.push(
        env.DB.prepare(
          `INSERT OR REPLACE INTO hotels
          (id,name,city,type,grade,rating,price,reviews,station_distance,amenities,
           free_cancellation,pay_at_hotel,breakfast,family_room,pet_friendly,pool,spa,chain,balcony)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`,
        ).bind(
          hotelId,
          name,
          city,
          i % 19 === 0 ? "Ryokan" : i % 11 === 0 ? "Resort" : "Hotel",
          3 + (i % 3),
          7.1 + (i % 28) / 10,
          70000 + (i % 48) * 5000,
          80 + ((i * 97) % 4900),
          80 + ((i * 73) % 1400),
          JSON.stringify(amenities),
          i % 3 ? 1 : 0,
          i % 4 ? 1 : 0,
          i % 2 ? 0 : 1,
          i % 3 ? 0 : 1,
          i % 7 ? 0 : 1,
          i % 5 ? 0 : 1,
          i % 6 ? 0 : 1,
          null,
          i % 4 ? 0 : 1,
        ),
      );
      for (let r = 0; r < 3; r++) {
        roomWrites.push(
          env.DB.prepare(
            `INSERT OR REPLACE INTO room_inventory
            (id,hotel_id,name,bed_type,view_type,size_sqm,capacity,breakfast,
             free_cancellation,pay_at_hotel,spa_access,bathtub,smoking,units_left,
             price_modifier,pool_access,pet_friendly,balcony)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`,
          ).bind(
            `R${String(i + 1).padStart(4, "0")}_${r + 1}`,
            hotelId,
            roomLabels[r].name,
            roomLabels[r].bed,
            roomLabels[r].view,
            24 + r * 9,
            2 + r,
            (i + r) % 2 ? 0 : 1,
            (i + r) % 3 ? 1 : 0,
            (i + r) % 4 ? 1 : 0,
            (i + r) % 3 ? 0 : 1,
            (i + r) % 3 ? 0 : 1,
            r === 0 ? 1 : 0,
            1 + ((i + r) % 4),
            r * 25000,
            (i + r) % 4 ? 0 : 1,
            (i + r) % 7 ? 0 : 1,
            (i + r) % 3 ? 0 : 1,
          ),
        );
      }
      i++;
    }
  }
  for (let n = 0; n < hotelWrites.length; n += 80)
    await env.DB.batch(hotelWrites.slice(n, n + 80));
  for (let n = 0; n < roomWrites.length; n += 80)
    await env.DB.batch(roomWrites.slice(n, n + 80));
}
async function identity(req: NextRequest) {
  let user = req.cookies.get("st_user")?.value,
    session = req.cookies.get("st_session")?.value,
    created = false;
  if (!user || !session) {
    user = id("USR");
    session = id("SES");
    await env.DB.batch([
      env.DB.prepare("INSERT INTO users VALUES(?,?,?)").bind(
        user,
        `익명여행자-${user.slice(-4)}`,
        now(),
      ),
      env.DB.prepare("INSERT INTO sessions VALUES(?,?,?,NULL)").bind(
        session,
        user,
        now(),
      ),
      evt(user, session, "session_start", "landing", null, null, {
        anonymous: true,
      }),
    ]);
    created = true;
  }
  return { user, session, created };
}
const evt = (
  u: string,
  s: string,
  name: string,
  page: string,
  search: any,
  hotel: any,
  props: any,
) =>
  env.DB.prepare("INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?)").bind(
    id("EVT"),
    u,
    s,
    search,
    hotel,
    name,
    page,
    JSON.stringify(props || {}),
    now(),
  );
function response(
  data: any,
  x: { user: string; session: string; created: boolean },
) {
  const r = NextResponse.json(data);
  if (x.created) {
    r.cookies.set("st_user", x.user, {
      httpOnly: true,
      sameSite: "lax",
      maxAge: 2592000,
    });
    r.cookies.set("st_session", x.session, {
      httpOnly: true,
      sameSite: "lax",
      maxAge: 2592000,
    });
  }
  return r;
}
// Agoda does not publish a filter-error rate. We therefore use a conservative,
// reproducible study calibration: 25% treatment sessions, with an expected
// population incidence of 8% per selected room option and 5% per keyword search.
const variant = (s: string) =>
  [...s].reduce((a, c) => a + c.charCodeAt(0), 0) % 4 === 0
    ? "mismatch"
    : "control";
const requestedRoomOptions = [
  "freeCancellation",
  "payAtHotel",
  "breakfast",
  "familyRoom",
  "petFriendly",
  "pool",
  "spa",
  "balcony",
  "bathtub",
  "nonSmoking",
  "cityView",
  "twinBed",
  "airConditioning",
  "kitchen",
  "washingMachine",
  "soundproof",
];
const mismatchFor = (session: string, hotel: string, option: string) =>
  variant(session) === "mismatch" &&
  [...`${session}:${hotel}:${option}`].reduce(
    (sum, char) => (sum * 31 + char.charCodeAt(0)) % 1009,
    7,
  ) %
    100 <
    (option.startsWith("keyword:") ? 20 : 32);
const availabilityHash = (value: string) =>
  [...value].reduce((sum, char) => (sum * 33 + char.charCodeAt(0)) % 10007, 17);
const roomLabels = [
  { name: "스탠다드 더블", bed: "퀸베드 1개", view: "시티뷰" },
  { name: "디럭스 트윈", bed: "싱글베드 2개", view: "가든뷰" },
  { name: "프리미엄 스위트", bed: "킹베드 1개", view: "파노라마뷰" },
];
const enrichHotel = (h: any) => {
  const n = Number(String(h.id).replace(/\D/g, "")) || 1;
  const subregions = HOTEL_SUBREGIONS[h.city] || ["도심"];
  const supplier = SUPPLIER_HOTEL_BY_NAME.get(String(h.name).toLowerCase());
  return {
    ...h,
    actual_data_available: supplier ? 1 : 0,
    actual_address: supplier?.address || "",
    actual_city: supplier?.sourceCity || "",
    actual_prefecture: supplier?.prefecture || "",
    actual_postal_code: supplier?.postalCode || "",
    actual_latitude: supplier?.latitude ?? "",
    actual_longitude: supplier?.longitude ?? "",
    actual_phone: supplier?.phone || "",
    actual_star_rating: supplier?.starRating ?? "",
    supplier_grade: supplier?.supplierGrade || "",
    supplier_hotel_code: supplier?.supplierHotelCode || "",
    rtx_code: supplier?.rtxCode || "",
    agoda_code: supplier?.agodaCode || "",
    expedia_code: supplier?.expediaCode || "",
    top_selling_rank: supplier?.topSellingRank ?? "",
    source_last_mapped_at: supplier?.lastMappingDate || "",
    actual_data_sources: supplier?.sources.join(" · ") || "",
    subregion: subregions[(n - 1) % 200 % subregions.length],
    parking: n % 3 ? 1 : 0,
    restaurant: n % 2 ? 1 : 0,
    gym: n % 4 ? 0 : 1,
    laundry: n % 3 ? 0 : 1,
    airport_shuttle: n % 7 ? 0 : 1,
    onsen: n % 8 ? 0 : 1,
    accessible: n % 5 ? 1 : 0,
    luggage_storage: n % 6 ? 1 : 0,
    front_desk_24h: n % 4 ? 1 : 0,
  };
};
async function livePlaceDetails(hotel: any) {
  const apiKey = String((env as any).GOOGLE_PLACES_API_KEY || "");
  if (!apiKey) return { available: false, reason: "api_key_unavailable" };
  try {
    const result = await fetch("https://places.googleapis.com/v1/places:searchText", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": apiKey,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount,places.websiteUri,places.googleMapsUri",
      },
      body: JSON.stringify({ textQuery: `${hotel.name}, ${hotel.city}, Japan`, languageCode: "ko" }),
    });
    if (!result.ok) {
      const legacy = await fetch(`https://maps.googleapis.com/maps/api/place/textsearch/json?query=${encodeURIComponent(`${hotel.name}, ${hotel.city}, Japan`)}&language=ko&region=jp&key=${encodeURIComponent(apiKey)}`);
      const legacyData = legacy.ok ? (await legacy.json()) as any : null;
      const oldPlace = legacyData?.results?.[0];
      if (!oldPlace) {
        const osmResponse = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&addressdetails=1&countrycodes=jp&q=${encodeURIComponent(`${hotel.name}, ${hotel.city}, Japan`)}`, {
          headers: { "User-Agent": "StayTraceResearch/1.0 (hotel research application)" },
        });
        const osmPlace = osmResponse.ok ? ((await osmResponse.json()) as any[])?.[0] : null;
        if (!osmPlace) return { available: false, reason: `places_${result.status}_${legacyData?.status || legacy.status}` };
        return {
          available: true, source: "OpenStreetMap Nominatim (live)", retrieved_at: now(),
          place_id: `${osmPlace.osm_type || ""}/${osmPlace.osm_id || ""}`,
          display_name: osmPlace.name || hotel.name, formatted_address: osmPlace.display_name || "",
          latitude: osmPlace.lat || "", longitude: osmPlace.lon || "", rating: "",
          user_rating_count: "", business_status: "", property_type: osmPlace.type || osmPlace.category || "",
          website_uri: "", google_maps_uri: osmPlace.osm_id ? `https://www.openstreetmap.org/${osmPlace.osm_type === "way" ? "way" : osmPlace.osm_type === "relation" ? "relation" : "node"}/${osmPlace.osm_id}` : "",
        };
      }
      return {
        available: true, source: "Google Places API (live)", retrieved_at: now(),
        place_id: oldPlace.place_id || "", display_name: oldPlace.name || hotel.name,
        formatted_address: oldPlace.formatted_address || "",
        latitude: oldPlace.geometry?.location?.lat ?? "", longitude: oldPlace.geometry?.location?.lng ?? "",
        rating: oldPlace.rating ?? "", user_rating_count: oldPlace.user_ratings_total ?? "",
        business_status: oldPlace.business_status || "", property_type: oldPlace.types?.[0] || "",
        website_uri: "", google_maps_uri: oldPlace.place_id ? `https://www.google.com/maps/place/?q=place_id:${oldPlace.place_id}` : "",
      };
    }
    const place = ((await result.json()) as any).places?.[0];
    if (!place) return { available: false, reason: "not_found" };
    return {
      available: true, source: "Google Places API (live)", retrieved_at: now(),
      place_id: place.id || "", display_name: place.displayName?.text || hotel.name,
      formatted_address: place.formattedAddress || "", latitude: place.location?.latitude ?? "",
      longitude: place.location?.longitude ?? "", rating: place.rating ?? "",
      user_rating_count: place.userRatingCount ?? "", business_status: place.businessStatus || "",
      property_type: place.primaryTypeDisplayName?.text || "", website_uri: place.websiteUri || "",
      google_maps_uri: place.googleMapsUri || "",
    };
  } catch {
    return { available: false, reason: "request_failed" };
  }
}
const syntheticReviews = (rawHotel: any) => {
  const h = enrichHotel(rawHotel),
    n = Number(String(h.id).replace(/\D/g, "")) || 1,
    cityName: Record<string, string> = {
      Tokyo: "도쿄",
      Osaka: "오사카",
      Kyoto: "교토",
      Fukuoka: "후쿠오카",
      Sapporo: "삿포로",
    },
    city = cityName[h.city] || h.city,
    closeToStation = Number(h.station_distance) <= 500,
    feature = h.spa
      ? "스파 시설을 이용하며 여행의 피로를 풀기 좋았습니다"
      : h.pool
        ? "수영장이 있어 숙소 안에서도 여유롭게 시간을 보냈습니다"
        : h.balcony
          ? "발코니가 있는 공간이 특히 인상적이었습니다"
          : h.breakfast
            ? "조식 구성이 무난하고 아침 일정을 시작하기 편했습니다"
            : "무료 Wi-Fi가 안정적이라 여행 정보를 확인하기 편했습니다",
    policy = h.free_cancellation
      ? "무료 취소가 가능한 상품을 고를 수 있어 일정 변경 부담이 적었습니다"
      : h.pay_at_hotel
        ? "현장 결제 상품이 있어 예약 조건을 비교하기 편했습니다"
        : "예약 전 취소 및 결제 조건을 꼼꼼히 확인하는 것이 좋겠습니다",
    typeName: Record<string, string> = {
      Hotel: "호텔",
      Ryokan: "료칸",
      Resort: "리조트",
      Apartment: "아파트형 숙소",
      Hostel: "호스텔",
      Guesthouse: "게스트하우스",
    },
    labels = typeName[h.type] || "숙소",
    templates = [
      {
        name: "민서 K.", country: "대한민국", delta: 0.4,
        title: "이동하기 편하고 관리가 잘 된 숙소",
        body: `${city} 여행 중 머물렀습니다. ${closeToStation ? `역에서 약 ${h.station_distance}m 거리라 짐을 들고 이동하기 편했고` : `역에서 약 ${h.station_distance}m로 조금 걸어야 했지만 주변을 둘러보기 좋았고`}, 객실과 공용 공간이 전반적으로 깔끔했습니다. ${feature}.`,
        stay: "커플 여행 · 2026년 7월",
      },
      {
        name: "유토 S.", country: "일본", delta: 0.1,
        title: `${labels}의 장점이 잘 드러난 숙박`,
        body: `${h.name}은(는) ${city} 일정을 소화하기에 무난한 위치였습니다. 직원 안내가 차분했고 객실 정돈 상태도 좋았습니다. ${policy}.`,
        stay: "출장 · 2026년 6월",
      },
      {
        name: "지현 P.", country: "대한민국", delta: -0.3,
        title: "장점이 분명하지만 조건 확인은 필요해요",
        body: `${feature}. 다만 객실 유형에 따라 제공되는 시설과 전망이 달라 보여 예약 전에 세부 옵션을 확인하는 편이 좋겠습니다. 전체적으로는 ${city} 관광 거점으로 만족스러웠습니다.`,
        stay: "친구와 여행 · 2026년 5월",
      },
      {
        name: "Emma R.", country: "호주", delta: 0.2,
        title: "조용하고 편안했던 도심 숙박",
        body: `밤에는 비교적 조용했고 침구도 편안했습니다. ${h.restaurant ? "숙소 내 레스토랑을 이용할 수 있어 식사 선택이 편했고" : "주변 식당을 찾아다니며 지역 분위기를 즐길 수 있었고"}, ${h.luggage_storage ? "체크아웃 뒤 짐 보관 서비스도 유용했습니다" : "체크아웃 뒤 짐 보관 가능 여부는 미리 문의하는 것이 좋습니다"}.`,
        stay: "1인 여행 · 2026년 4월",
      },
      {
        name: "준호 L.", country: "대한민국", delta: -0.1,
        title: "가격과 시설의 균형이 괜찮았습니다",
        body: `객실 가격대와 ${h.grade}성급 시설을 함께 고려하면 전반적인 균형이 괜찮았습니다. ${h.front_desk_24h ? "24시간 프런트가 있어 늦은 시간에도 안심됐고" : "늦은 도착이라면 프런트 운영 시간을 확인해야 하며"}, ${h.parking ? "주차장을 이용할 수 있다는 점도 편리했습니다" : "대중교통으로 방문하는 편이 더 편해 보였습니다"}.`,
        stay: "가족 여행 · 2026년 3월",
      },
    ];
  return templates.map((review, index) => {
    const rating = Math.max(6, Math.min(10, Number(h.rating) + review.delta));
    return {
      review_id: `V${String(h.id).replace(/^H/, "")}${index + 1}`,
      hotel_id: h.id,
      user_id: `RU${String(h.id).replace(/^H/, "")}${index + 1}`,
      name: review.name,
      country: review.country,
      rating: Number(rating.toFixed(1)),
      score: Number(rating.toFixed(1)),
      review_created_at: `2026-${String(3 + index).padStart(2, "0")}-${String(8 + (n + index * 3) % 19).padStart(2, "0")} 21:00:00 KST`,
      review_text: review.body,
      body: review.body,
      review_photo_url: "",
      title: review.title,
      stay: review.stay,
    };
  });
};
const analysisTableNames = [
  "HOTEL",
  "ROOM",
  "SEARCH",
  "SEARCH_FILTER",
  "USER",
  "EVENT",
  "SEARCH_RESULT",
  "BOOKING",
] as const;
const analysisIdKey = (table: string) => `${table.toLowerCase()}_id`;
const parseObject = (value: any) => {
  try {
    return JSON.parse(value || "{}");
  } catch {
    return {};
  }
};
const ADMIN_DELETE_CODE_HASH = "267515e716eda554bd6f351dde746d718be2c06f0c613e99501d659d535dbd1c";
const validAdminCode = async (value: unknown) => {
  const bytes = new TextEncoder().encode(String(value || "").trim());
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("") === ADMIN_DELETE_CODE_HASH;
};
const koreanSearchAliases: Record<string, string> = {
  도쿄: "tokyo", 동경: "tokyo", 오사카: "osaka", 교토: "kyoto",
  후쿠오카: "fukuoka", 삿포로: "sapporo", 신주쿠: "shinjuku",
  시부야: "shibuya", 우에노: "ueno", 아사쿠사: "asakusa",
  긴자: "ginza", 니혼바시: "nihombashi", 하네다: "haneda",
  난바: "namba", 우메다: "umeda", 도톤보리: "dotonbori",
  기온: "gion", 하카타: "hakata", 텐진: "tenjin",
  스스키노: "susukino", 오도리: "odori", 하얏트: "hyatt",
  힐튼: "hilton", 메리어트: "marriott", 프린스: "prince",
  인터컨티넨탈: "intercontinental", 리츠칼튼: "ritz carlton",
  만다린: "mandarin", 도큐: "tokyu", 미츠이: "mitsui",
  리치몬드: "richmond", 그란비아: "granvia", 닛코: "nikko",
  몬테레이: "monterey", 료칸: "ryokan", 리조트: "resort",
  호스텔: "hostel", 게스트하우스: "guesthouse", 호텔: "hotel",
  무료와이파이: "무료 wi-fi", 와이파이: "wi-fi", 조식: "조식",
  수영장: "수영장", 스파: "스파", 발코니: "발코니", 베란다: "발코니",
  온천: "온천", 주차: "주차", 레스토랑: "레스토랑",
  피트니스: "피트니스", 공항셔틀: "공항 셔틀",
};
const keywordTokens = (value: string) => {
  let normalized = value.toLocaleLowerCase().trim();
  for (const [korean, translated] of Object.entries(koreanSearchAliases))
    normalized = normalized.replaceAll(korean, ` ${translated} `);
  return normalized.split(/\s+/).filter(Boolean);
};
async function analysisDatasets() {
  const [hotels, rooms, searches, users, events, reservations, deleted] =
    await Promise.all([
      env.DB.prepare("SELECT * FROM hotels ORDER BY id").all(),
      env.DB.prepare("SELECT * FROM room_inventory ORDER BY hotel_id,id").all(),
      env.DB.prepare("SELECT * FROM searches ORDER BY created_at DESC").all(),
      env.DB.prepare("SELECT * FROM users ORDER BY created_at DESC").all(),
      env.DB.prepare("SELECT * FROM events ORDER BY created_at DESC").all(),
      env.DB.prepare("SELECT * FROM reservations ORDER BY created_at DESC").all(),
      env.DB.prepare("SELECT * FROM admin_deleted_rows ORDER BY deleted_at DESC").all(),
    ]);
  const profileByUser = new Map<string, any>();
  for (const event of events.results as any[]) {
    if (event.name === "participant_profile_submit" && !profileByUser.has(event.user_id))
      profileByUser.set(event.user_id, parseObject(event.properties));
  }
  const searchConditions = new Map<string, any>();
  for (const search of searches.results as any[])
    searchConditions.set(search.id, parseObject(search.conditions));
  const hotelById = new Map<string, any>(
    (hotels.results as any[]).map((hotel) => [hotel.id, hotel]),
  );
  const roomByHotel = new Map<string, any>();
  for (const room of rooms.results as any[])
    if (!roomByHotel.has(room.hotel_id)) roomByHotel.set(room.hotel_id, room);
  const bookingEventByReservation = new Map<string, any>();
  for (const event of events.results as any[]) {
    if (event.name !== "booking_complete") continue;
    const properties = parseObject(event.properties);
    if (properties.reservation) bookingEventByReservation.set(properties.reservation, properties);
  }
  const amenityKeys = [
    "freeCancellation", "payAtHotel", "breakfast", "familyRoom", "petFriendly",
    "pool", "spa", "balcony", "bathtub", "nonSmoking", "cityView", "twinBed",
    "airConditioning", "kitchen", "washingMachine", "soundproof", "parking",
    "restaurant", "gym", "laundry", "airportShuttle", "onsen", "accessible",
    "luggageStorage", "frontDesk24h",
  ];
  const datasets: Record<string, any[]> = {
    HOTEL: (hotels.results as any[]).map((h) => {
      const x = enrichHotel(h);
      return {
        hotel_id: h.id, hotel_name: h.name, city_name: h.city,
        grade: h.grade, hotel_address: x.actual_address || `${h.city} ${x.subregion}`,
        user_rating: h.rating, review_count: h.reviews, property_type: h.type,
        actual_address: x.actual_address, actual_city: x.actual_city,
        actual_prefecture: x.actual_prefecture, actual_postal_code: x.actual_postal_code,
        actual_latitude: x.actual_latitude, actual_longitude: x.actual_longitude,
        actual_phone: x.actual_phone, actual_star_rating: x.actual_star_rating,
        supplier_hotel_code: x.supplier_hotel_code, rtx_code: x.rtx_code,
        agoda_code: x.agoda_code, expedia_code: x.expedia_code,
        top_selling_rank: x.top_selling_rank, source_last_mapped_at: x.source_last_mapped_at,
        actual_data_sources: x.actual_data_sources,
      };
    }),
    ROOM: (rooms.results as any[]).map((room) => {
      const h = hotelById.get(room.hotel_id) || {};
      return {
        room_id: room.id, hotel_id: room.hotel_id,
        guest_count: room.capacity, room_count: room.units_left,
        room_options: JSON.stringify({ bed_type: room.bed_type, view_type: room.view_type,
          size_sqm: room.size_sqm, breakfast: Boolean(room.breakfast),
          spa: Boolean(room.spa_access), pool: Boolean(room.pool_access),
          balcony: Boolean(room.balcony), bathtub: Boolean(room.bathtub),
          pet_friendly: Boolean(room.pet_friendly), smoking: Boolean(room.smoking) }),
        pay_later_flag: Boolean(room.pay_at_hotel),
        free_cancel_flag: Boolean(room.free_cancellation),
        room_price: Number(h.price || 0) + Number(room.price_modifier || 0),
        room_type: room.name,
      };
    }),
    SEARCH: (searches.results as any[]).map((s) => {
      const c = searchConditions.get(s.id) || {};
      return { search_id: s.id, session_id: s.session_id, search_time: koreanDateTime(s.created_at),
        query_text: c.keyword || "", checkin_date: c.checkin || "",
        checkout_date: c.checkout || "", total_result_count: s.result_count,
        sort_option: c.sort || "", guest_count: c.guests || "",
        destination: [c.city, c.subregion].filter(Boolean).join(" · ") };
    }),
    SEARCH_FILTER: (searches.results as any[]).map((s) => {
      const c = searchConditions.get(s.id) || {};
      return { search_filter_id: `F${s.id}`, search_id: s.id,
        property_type: c.type || "", property_grade: c.grade || "",
        user_rating_min: c.rating || "", price: c.maxPrice || "",
        amenity_count: amenityKeys.filter((key) => c[key]).length,
        transportation: c.nearStation ? `${c.nearStation}m 이내` : "",
        region: [c.city, c.subregion].filter(Boolean).join(" · ") };
    }),
    USER: (users.results as any[]).map((u) => {
      const p = profileByUser.get(u.id) || {};
      return { user_id: u.id, user_name: p.participant_name || u.name,
        age_group: p.age_group || "", email: p.email || "", signup_at: koreanDateTime(u.created_at) };
    }),
    EVENT: (events.results as any[]).map((e) => {
      const p = parseObject(e.properties);
      return { event_id: e.id, session_id: e.session_id, event_type: e.name,
        event_at: koreanDateTime(e.created_at), hotel_id: e.hotel_id || "",
        search_filter_id: e.search_id ? `F${e.search_id}` : "",
        search_id: e.search_id || "", user_id: e.user_id,
        rating: p.rating ?? p.score ?? "",
        review_completed_at: p.review_text ? koreanDateTime(e.created_at) : "",
        review_text: p.review_text || "", device: p.device || "" };
    }),
    SEARCH_RESULT: (events.results as any[])
      .filter((e) => e.name === "hotel_impression" && e.search_id && e.hotel_id)
      .map((e) => {
        const h = hotelById.get(e.hotel_id) || {}, p = parseObject(e.properties);
        return {
          search_result_id: `X${e.id}`, search_id: e.search_id,
          hotel_id: e.hotel_id, room_id: roomByHotel.get(e.hotel_id)?.id || "",
          result_score: Math.max(0, 101 - Number(p.rank || 0)),
          result_rank: p.rank || "", price_rank: "",
        };
      }),
    BOOKING: (reservations.results as any[]).map((r) => {
      const c = searchConditions.get(r.search_id) || {},
        bookingEvent = bookingEventByReservation.get(r.id) || {},
        cancelDate = c.checkin ? new Date(`${c.checkin}T00:00:00.000Z`) : null;
      if (cancelDate && !Number.isNaN(cancelDate.getTime())) cancelDate.setUTCDate(cancelDate.getUTCDate() - 2);
      return { booking_id: r.id, user_id: r.user_id, hotel_id: r.hotel_id,
        room_id: bookingEvent.room_id || "",
        booking_status: r.status, booking_amount: r.total_price,
        booking_at: koreanDateTime(r.created_at), checkin_date: c.checkin || "",
        checkout_date: c.checkout || "", guest_count: c.guests || "",
        room_count: c.rooms || "",
        cancellation_deadline: cancelDate ? cancelDate.toISOString().slice(0, 10) : "" };
    }),
  };
  const dataOrigins: Record<string, string> = {
    HOTEL: "호텔명·도시 및 실제정보 컬럼=사용자 제공 일본 호텔 자료(매칭된 호텔) / 가격·이용자평점·리뷰수·시설·재고=가상",
    ROOM: "전체 가상 시뮬레이션",
    SEARCH: "실제 사용자 입력·검색 로그",
    SEARCH_FILTER: "실제 사용자 선택값",
    USER: "실제 참여자 입력값",
    EVENT: "실제 행동 로그",
    SEARCH_RESULT: "실제 노출 로그 / 점수·순위는 실험용",
    BOOKING: "전체 가상 예약 시뮬레이션",
  };
  for (const [table, rows] of Object.entries(datasets))
    for (const row of rows) row.data_origin = dataOrigins[table] || "";
  const resultsBySearch = new Map<string, any[]>();
  for (const result of datasets.SEARCH_RESULT) {
    const rows = resultsBySearch.get(result.search_id) || [];
    rows.push(result);
    resultsBySearch.set(result.search_id, rows);
  }
  for (const rows of resultsBySearch.values()) {
    const priceOrder = [...rows].sort((a, b) =>
      Number(hotelById.get(a.hotel_id)?.price || 0) -
      Number(hotelById.get(b.hotel_id)?.price || 0),
    );
    const priceRanks = new Map(priceOrder.map((row, index) => [row.search_result_id, index + 1]));
    for (const row of rows) row.price_rank = priceRanks.get(row.search_result_id) || "";
  }
  const deletedKeys = new Set((deleted.results as any[]).map((r) => `${r.table_name}:${r.row_id}`));
  for (const table of analysisTableNames) {
    const idKey = analysisIdKey(table);
    datasets[table] = datasets[table].filter((row) => !deletedKeys.has(`${table}:${row[idKey]}`));
  }
  const ownership: Record<string, Record<string, string>> = {
    HOTEL: {}, ROOM: {},
    USER: Object.fromEntries((users.results as any[]).map((u) => [u.id, u.id])),
    SEARCH: Object.fromEntries((searches.results as any[]).map((s) => [s.id, s.user_id])),
    SEARCH_FILTER: Object.fromEntries((searches.results as any[]).map((s) => [`F${s.id}`, s.user_id])),
    EVENT: Object.fromEntries((events.results as any[]).map((e) => [e.id, e.user_id])),
    SEARCH_RESULT: Object.fromEntries((events.results as any[])
      .filter((e) => e.name === "hotel_impression").map((e) => [`X${e.id}`, e.user_id])),
    BOOKING: Object.fromEntries((reservations.results as any[]).map((r) => [r.id, r.user_id])),
  };
  const userOptions = (users.results as any[]).map((u) => ({
    user_id: u.id,
    user_name: profileByUser.get(u.id)?.participant_name || u.name,
  }));
  return {
    datasets,
    deleted: (deleted.results as any[]).map((row) => ({
      ...row,
      deleted_at: koreanDateTime(row.deleted_at),
    })),
    ownership,
    userOptions,
  };
}
export async function GET(req: NextRequest) {
  await init();
  const x = await identity(req),
    mode = req.nextUrl.searchParams.get("mode");
  if (mode === "admin") {
    if (!(await validAdminCode(req.headers.get("x-admin-code"))))
      return response({ error: "invalid_admin_code" }, x);
    const [events, counts, assignments, bookings, selections, searchCounts] =
        await Promise.all([
          env.DB.prepare(
            "SELECT * FROM events ORDER BY created_at DESC LIMIT 300",
          ).all(),
          env.DB.prepare(
            "SELECT (SELECT COUNT(*) FROM users) users,(SELECT COUNT(*) FROM sessions) sessions,(SELECT COUNT(*) FROM searches) searches,(SELECT COUNT(*) FROM reservations) reservations,(SELECT COUNT(*) FROM events) events",
          ).first(),
          env.DB.prepare(
            "SELECT session_id,properties FROM events WHERE name='experiment_assignment'",
          ).all(),
          env.DB.prepare(
            "SELECT DISTINCT session_id FROM events WHERE name='booking_complete'",
          ).all(),
          env.DB.prepare(
            "SELECT DISTINCT session_id FROM events WHERE name='room_select'",
          ).all(),
          env.DB.prepare(
            "SELECT session_id,COUNT(*) searches FROM searches GROUP BY session_id",
          ).all(),
        ]),
      booked = new Set((bookings.results as any[]).map((v) => v.session_id)),
      selected = new Set(
        (selections.results as any[]).map((v) => v.session_id),
      ),
      searchMap = new Map(
        (searchCounts.results as any[]).map((v) => [
          v.session_id,
          Number(v.searches),
        ]),
      ),
      groups: any = {
        control: {
          sessions: new Set(),
          booked: new Set(),
          selected: new Set(),
        },
        mismatch: {
          sessions: new Set(),
          booked: new Set(),
          selected: new Set(),
        },
      };
    for (const a of assignments.results as any[]) {
      const v = JSON.parse(a.properties).variant || "control";
      groups[v].sessions.add(a.session_id);
      if (booked.has(a.session_id)) groups[v].booked.add(a.session_id);
      if (selected.has(a.session_id)) groups[v].selected.add(a.session_id);
    }
    const experiment = Object.fromEntries(
      Object.entries(groups).map(([k, v]: any) => {
        const searches = [...v.sessions].map((s: any) => searchMap.get(s) || 0);
        return [
          k,
          {
            sessions: v.sessions.size,
            selections: v.selected.size,
            bookings: v.booked.size,
            selectionRate: v.sessions.size
              ? Math.round((v.selected.size / v.sessions.size) * 1000) / 10
              : 0,
            conversion: v.sessions.size
              ? Math.round((v.booked.size / v.sessions.size) * 1000) / 10
              : 0,
            avgSearches: searches.length
              ? Math.round(
                  (searches.reduce((a: number, b: number) => a + b, 0) /
                    searches.length) *
                    10,
                ) / 10
              : 0,
          },
        ];
      }),
    );
    const dataConsole = await analysisDatasets();
    return response({
      events: (events.results as any[]).map((event) => ({
        ...event,
        created_at: koreanDateTime(event.created_at),
      })),
      counts,
      experiment,
      timezone: "Asia/Seoul",
      ...dataConsole,
    }, x);
  }
  const hotels = await env.DB.prepare("SELECT * FROM hotels").all();
  return response({ hotels: hotels.results }, x);
}
export async function POST(req: NextRequest) {
  await init();
  const x = await identity(req),
    b = (await req.json()) as any;
  if (String(b.action || "").startsWith("admin_") &&
      !(await validAdminCode(req.headers.get("x-admin-code"))))
    return response({ error: "invalid_admin_code" }, x);
  if (b.action === "admin_delete") {
    if (!analysisTableNames.includes(b.table))
      return response({ error: "지원하지 않는 테이블입니다." }, x);
    const { datasets, ownership } = await analysisDatasets(), idKey = analysisIdKey(String(b.table));
    const row = datasets[b.table].find((item: any) => item[idKey] === b.rowId);
    if (!row) return response({ error: "데이터를 찾을 수 없습니다." }, x);
    await env.DB.prepare("INSERT OR REPLACE INTO admin_deleted_rows(table_name,row_id,snapshot,deleted_at,deleted_by,owner_user_id) VALUES(?,?,?,?,?,?)")
      .bind(b.table, b.rowId, JSON.stringify(row), now(), x.user,
        ownership[b.table]?.[b.rowId] || "").run();
    return response({ ok: true }, x);
  }
  if (b.action === "admin_bulk_delete") {
    const items = Array.isArray(b.items) ? b.items.slice(0, 5000) : [];
    const { datasets, ownership } = await analysisDatasets();
    const writes = [];
    for (const item of items) {
      if (!analysisTableNames.includes(item.table)) continue;
      const idKey = analysisIdKey(String(item.table));
      const row = datasets[item.table]?.find((entry: any) => entry[idKey] === item.rowId);
      if (!row) continue;
      writes.push(env.DB.prepare("INSERT OR REPLACE INTO admin_deleted_rows(table_name,row_id,snapshot,deleted_at,deleted_by,owner_user_id) VALUES(?,?,?,?,?,?)")
        .bind(item.table, item.rowId, JSON.stringify(row), now(), x.user,
          ownership[item.table]?.[item.rowId] || ""));
    }
    for (let index = 0; index < writes.length; index += 80)
      await env.DB.batch(writes.slice(index, index + 80));
    return response({ ok: true, affected: writes.length }, x);
  }
  if (b.action === "admin_restore") {
    await env.DB.prepare("DELETE FROM admin_deleted_rows WHERE table_name=? AND row_id=?")
      .bind(b.table, b.rowId).run();
    return response({ ok: true }, x);
  }
  if (b.action === "admin_bulk_restore") {
    const items = Array.isArray(b.items) ? b.items.slice(0, 5000) : [];
    const writes = items.map((item: any) =>
      env.DB.prepare("DELETE FROM admin_deleted_rows WHERE table_name=? AND row_id=?")
        .bind(item.table, item.rowId));
    for (let index = 0; index < writes.length; index += 80)
      await env.DB.batch(writes.slice(index, index + 80));
    return response({ ok: true, affected: writes.length }, x);
  }
  if (b.action === "search") {
    const c = b.conditions,
      all = (
        c.city
          ? await env.DB.prepare("SELECT * FROM hotels WHERE city=?")
              .bind(c.city)
              .all()
          : await env.DB.prepare("SELECT * FROM hotels").all()
      ).results.map(enrichHotel) as any[],
      eligible = all.filter(
        (h) =>
          (!c.type || h.type === c.type) &&
          (!c.subregion || h.subregion === c.subregion) &&
          (!c.rating || h.rating >= +c.rating) &&
          (!c.maxPrice || h.price <= +c.maxPrice) &&
          (!c.freeCancellation || h.free_cancellation) &&
          (!c.payAtHotel || h.pay_at_hotel) &&
          (!c.breakfast || h.breakfast) &&
          (!c.familyRoom || h.family_room) &&
          (!c.petFriendly || h.pet_friendly) &&
          (!c.pool || h.pool) &&
          (!c.spa || h.spa) &&
          (!c.balcony || h.balcony) &&
          (!c.parking || h.parking) &&
          (!c.restaurant || h.restaurant) &&
          (!c.gym || h.gym) &&
          (!c.laundry || h.laundry) &&
          (!c.airportShuttle || h.airport_shuttle) &&
          (!c.onsen || h.onsen) &&
          (!c.accessible || h.accessible) &&
          (!c.luggageStorage || h.luggage_storage) &&
          (!c.frontDesk24h || h.front_desk_24h) &&
          (!c.nearStation || h.station_distance <= Number(c.nearStation)) &&
          (!c.kitchen || Number(h.id.replace(/\D/g, "")) % 4 !== 0) &&
          (!c.washingMachine || Number(h.id.replace(/\D/g, "")) % 3 === 0) &&
          (!c.soundproof || Number(h.id.replace(/\D/g, "")) % 2 === 0) &&
          (!c.chain || h.chain === c.chain),
      );
    const keyword = String(c.keyword || "").trim().toLocaleLowerCase(),
      terms = keywordTokens(keyword),
      correctMatches = eligible.filter(
        (h) => {
          const searchable = [
            h.name, h.city, h.subregion, h.type, h.amenities,
            h.onsen ? "온천" : "", h.parking ? "주차" : "",
            h.restaurant ? "레스토랑" : "", h.gym ? "피트니스" : "",
            h.airport_shuttle ? "공항 셔틀" : "",
          ].join(" ").toLocaleLowerCase();
          return !keyword || terms.every((term) => searchable.includes(term));
        },
      ),
      keywordError = Boolean(
        keyword && mismatchFor(x.session, c.city || "ALL_JAPAN", `keyword:${keyword}`),
      ),
      omittedHotels = keywordError && correctMatches.length ? [correctMatches[0]] : [],
      injectedHotels = keywordError
        ? eligible
            .filter((h) => !correctMatches.some((match) => match.id === h.id))
            .slice(0, correctMatches.length ? 1 : 2)
        : [],
      hotels = keywordError
        ? [...correctMatches.slice(omittedHotels.length), ...injectedHotels]
        : correctMatches;
    const sorters: Record<string, (a: any, b: any) => number> = {
      rating: (a, b) => b.rating - a.rating || b.reviews - a.reviews,
      reviews: (a, b) => b.reviews - a.reviews || b.rating - a.rating,
      price: (a, b) => a.price - b.price || b.rating - a.rating,
      price_high: (a, b) => b.price - a.price || b.rating - a.rating,
    };
    hotels.sort(sorters[c.sort] || sorters.rating);
    const search = id("SRC");
    await env.DB.batch([
      env.DB.prepare("INSERT INTO searches VALUES(?,?,?,?,?,?,?)").bind(
        search,
        x.user,
        x.session,
        b.parentId || null,
        now(),
        JSON.stringify(c),
        hotels.length,
      ),
      evt(
        x.user,
        x.session,
        "search_submit",
        b.trigger === "filters_apply_button" ? "results" : "search",
        search,
        null,
        { ...c, submit_trigger: b.trigger || "search_button" },
      ),
      ...(keyword
        ? [
            evt(
              x.user,
              x.session,
              keywordError
                ? "keyword_search_error_exposure"
                : "keyword_search_result",
              "results",
              search,
              null,
              {
                keyword: c.keyword,
                normalized_keyword_terms: terms,
                variant: variant(x.session),
                error: keywordError,
                treatment_share: 25,
                conditional_error_rate: 20,
                estimated_population_error_rate: 5,
                correct_match_count: correctMatches.length,
                shown_count: hotels.length,
                omitted_hotel_ids: omittedHotels.map((h) => h.id),
                injected_hotel_ids: injectedHotels.map((h) => h.id),
              },
            ),
          ]
        : []),
      ...hotels.map((h, i) =>
        evt(x.user, x.session, "hotel_impression", "results", search, h.id, {
          rank: i + 1,
        }),
      ),
    ]);
    return response(
      {
        searchId: search,
        hotels: hotels.map((h) => {
          return {
            ...h,
            amenities: JSON.stringify([
              "무료 Wi-Fi",
              ...(h.breakfast ? ["조식"] : []),
              ...(h.pool ? ["수영장"] : []),
              ...(h.spa ? ["스파"] : []),
              ...(h.balcony ? ["발코니"] : []),
            ]),
          };
        }),
      },
      x,
    );
  }
  if (b.action === "rooms") {
    const v = variant(x.session),
      checkin = String(b.conditions?.checkin || "2026-01-01"),
      checkout = String(b.conditions?.checkout || "2026-01-02"),
      stayKey = `${b.hotelId}:${checkin}:${checkout}`,
      soldOutIndex = availabilityHash(stayKey) % 3,
      secondSoldOutIndex =
        availabilityHash(`${stayKey}:extra`) % 5 === 0
          ? (soldOutIndex + 1) % 3
          : -1,
      selectedOptions = requestedRoomOptions.filter(
        (option) => b.conditions?.[option],
      ),
      mismatchOptions = selectedOptions.filter((option) =>
        mismatchFor(x.session, b.hotelId, option),
      ),
      base = (
        await env.DB.prepare("SELECT * FROM room_inventory WHERE hotel_id=?")
          .bind(b.hotelId)
          .all()
      ).results as any[],
      rooms = base.map((r, index) => {
        const label = roomLabels[Math.max(0, Number(r.id.slice(-1)) - 1)];
        const available =
          index !== soldOutIndex && index !== secondSoldOutIndex;
        const room: any = {
          ...r,
          name: label.name,
          bed_type: label.bed,
          view_type: label.view,
          family_room: r.capacity >= 4 ? 1 : 0,
          air_conditioning: 1,
          kitchen:
            (Number(r.id.slice(-1)) + Number(r.hotel_id.slice(-2))) % 4 === 0
              ? 1
              : 0,
          washing_machine: Number(r.hotel_id.slice(-2)) % 3 === 0 ? 1 : 0,
          soundproof: Number(r.hotel_id.slice(-2)) % 2 === 0 ? 1 : 0,
          city_view: Number(r.id.slice(-1)) === 1 ? 1 : 0,
          twin_bed: Number(r.id.slice(-1)) === 2 ? 1 : 0,
          non_smoking: r.smoking ? 0 : 1,
          available,
          availability_reason: available
            ? null
            : `${checkin}~${checkout} 기간 예약 마감`,
          units_left: available ? r.units_left : 0,
        };
        const fields: Record<string, string> = {
          freeCancellation: "free_cancellation",
          payAtHotel: "pay_at_hotel",
          breakfast: "breakfast",
          familyRoom: "family_room",
          petFriendly: "pet_friendly",
          pool: "pool_access",
          spa: "spa_access",
          balcony: "balcony",
          bathtub: "bathtub",
          nonSmoking: "non_smoking",
          cityView: "city_view",
          twinBed: "twin_bed",
          airConditioning: "air_conditioning",
          kitchen: "kitchen",
          washingMachine: "washing_machine",
          soundproof: "soundproof",
        };
        for (const option of selectedOptions) {
          const field = fields[option];
          room[field] = mismatchOptions.includes(option)
            ? 0
            : index === 0
              ? 1
              : room[field];
        }
        if (mismatchOptions.includes("familyRoom")) room.capacity = 2;
        if (
          b.conditions?.familyRoom &&
          !mismatchOptions.includes("familyRoom") &&
          index === 0
        )
          room.capacity = Math.max(4, room.capacity);
        return room;
      }),
      mismatch = mismatchOptions.length > 0;
    await env.DB.batch([
      evt(
        x.user,
        x.session,
        "experiment_assignment",
        "detail",
        b.searchId,
        b.hotelId,
        {
          experiment: "search_room_option_consistency",
          variant: v,
          requested_options: selectedOptions,
          mismatch_options: mismatchOptions,
          treatment_share: 25,
          conditional_mismatch_rate: 32,
          estimated_population_mismatch_rate: 8,
        },
      ),
      evt(
        x.user,
        x.session,
        mismatch ? "option_mismatch_exposure" : "room_option_view",
        "detail",
        b.searchId,
        b.hotelId,
        {
          variant: v,
          requested_options: selectedOptions,
          mismatch_options: mismatchOptions,
          room_count: rooms.length,
          available_room_count: rooms.filter((r) => r.available).length,
          unavailable_room_count: rooms.filter((r) => !r.available).length,
          checkin,
          checkout,
        },
      ),
    ]);
    const hotelRecord = await env.DB.prepare("SELECT * FROM hotels WHERE id=?")
      .bind(b.hotelId)
      .first();
    return response(
      {
        rooms,
        actualHotel: hotelRecord ? await livePlaceDetails(hotelRecord) : { available: false, reason: "not_found" },
        reviews: hotelRecord ? syntheticReviews(hotelRecord) : [],
        variant: v,
        mismatchOptions,
      },
      x,
    );
  }
  if (b.action === "event") {
    if (b.name === "participant_logout") {
      await env.DB.batch([
        evt(x.user, x.session, b.name, b.page || "app", null, null, b.properties),
        env.DB.prepare("UPDATE sessions SET ended_at=? WHERE id=?").bind(now(), x.session),
      ]);
      const nextUser = id("USR"), nextSession = id("SES");
      await env.DB.batch([
        env.DB.prepare("INSERT INTO users VALUES(?,?,?)")
          .bind(nextUser, `익명여행자-${nextUser.slice(-4)}`, now()),
        env.DB.prepare("INSERT INTO sessions VALUES(?,?,?,NULL)")
          .bind(nextSession, nextUser, now()),
        evt(nextUser, nextSession, "session_start", "landing", null, null, {
          anonymous: true,
          after_logout: true,
        }),
      ]);
      x.user = nextUser;
      x.session = nextSession;
      x.created = true;
      return response({ ok: true }, x);
    }
    if (b.name === "participant_profile_submit") {
      const displayName = String(b.properties?.participant_name || "").normalize("NFKC").trim(),
        normalizedName = displayName.toLocaleLowerCase().replace(/\s+/g, " ");
      if (normalizedName) {
        await env.DB.prepare(
          "INSERT OR IGNORE INTO participant_identities VALUES(?,?,?,?)",
        ).bind(normalizedName, x.user, displayName, now()).run();
        const identityRow = await env.DB.prepare(
          "SELECT user_id FROM participant_identities WHERE normalized_name=?",
        ).bind(normalizedName).first<{ user_id: string }>();
        const canonicalUser = identityRow?.user_id || x.user;
        if (canonicalUser === x.user) {
          await env.DB.prepare("UPDATE users SET name=? WHERE id=?")
            .bind(displayName, x.user).run();
        } else {
          await env.DB.batch([
            env.DB.prepare("UPDATE sessions SET user_id=? WHERE id=?")
              .bind(canonicalUser, x.session),
            env.DB.prepare("UPDATE events SET user_id=? WHERE session_id=?")
              .bind(canonicalUser, x.session),
            env.DB.prepare("UPDATE searches SET user_id=? WHERE session_id=?")
              .bind(canonicalUser, x.session),
            env.DB.prepare("UPDATE reservations SET user_id=? WHERE session_id=?")
              .bind(canonicalUser, x.session),
          ]);
          x.user = canonicalUser;
          x.created = true;
        }
      }
    }
    await evt(
      x.user,
      x.session,
      b.name,
      b.page || "app",
      b.searchId || null,
      b.hotelId || null,
      b.properties,
    ).run();
    return response({ ok: true }, x);
  }
  if (b.action === "booking") {
    const stayKey = `${b.hotelId}:${b.conditions?.checkin || "2026-01-01"}:${
      b.conditions?.checkout || "2026-01-02"
    }`;
    const soldOutIndex = availabilityHash(stayKey) % 3;
    const secondSoldOutIndex =
      availabilityHash(`${stayKey}:extra`) % 5 === 0
        ? (soldOutIndex + 1) % 3
        : -1;
    const requestedRoomIndex = Math.max(
      0,
      Number(String(b.roomId).slice(-1)) - 1,
    );
    if (
      requestedRoomIndex === soldOutIndex ||
      requestedRoomIndex === secondSoldOutIndex
    ) {
      await evt(
        x.user,
        x.session,
        "booking_blocked_unavailable",
        "booking",
        b.searchId,
        b.hotelId,
        { room_id: b.roomId, stay: b.conditions },
      ).run();
      return response({ error: "room_unavailable" }, x);
    }
    const reservation = id("RSV"),
      v = variant(x.session);
    await env.DB.batch([
      env.DB.prepare("INSERT INTO reservations VALUES(?,?,?,?,?,?,?,?)").bind(
        reservation,
        x.user,
        x.session,
        b.searchId,
        b.hotelId,
        b.totalPrice,
        "confirmed",
        now(),
      ),
      evt(
        x.user,
        x.session,
        "booking_complete",
        "booking",
        b.searchId,
        b.hotelId,
        {
          reservation,
          totalPrice: b.totalPrice,
          room_id: b.roomId,
          variant: v,
        },
      ),
    ]);
    return response({ reservation }, x);
  }
  return response({ error: "unknown action" }, x);
}
