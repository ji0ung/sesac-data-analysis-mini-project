"use client";
import { useEffect, useRef, useState } from "react";
import { HOTEL_SUBREGIONS } from "./hotel-data";
type H = {
  id: string;
  name: string;
  city: string;
  subregion: string;
  type: string;
  grade: number;
  rating: number;
  price: number;
  reviews: number;
  station_distance: number;
  amenities: string;
  free_cancellation: number;
  pay_at_hotel: number;
  breakfast: number;
  family_room: number;
  pet_friendly: number;
  pool: number;
  spa: number;
  balcony: number;
  parking: number;
  restaurant: number;
  gym: number;
  laundry: number;
  airport_shuttle: number;
  onsen: number;
  accessible: number;
  luggage_storage: number;
  front_desk_24h: number;
  chain: string | null;
  actual_data_available: number;
  actual_address: string;
  actual_city: string;
  actual_prefecture: string;
  actual_postal_code: string;
  actual_latitude: number | string;
  actual_longitude: number | string;
  actual_phone: string;
  actual_star_rating: number | string;
  supplier_grade: string;
  supplier_hotel_code: string;
  rtx_code: string;
  agoda_code: string;
  expedia_code: string;
  top_selling_rank: number | string;
  source_last_mapped_at: string;
  actual_data_sources: string;
};
type R = {
  id: string;
  name: string;
  bed_type: string;
  view_type: string;
  size_sqm: number;
  capacity: number;
  breakfast: number;
  free_cancellation: number;
  pay_at_hotel: number;
  spa_access: number;
  pool_access: number;
  pet_friendly: number;
  balcony: number;
  family_room: number;
  bathtub: number;
  smoking: number;
  units_left: number;
  price_modifier: number;
  air_conditioning: number;
  kitchen: number;
  washing_machine: number;
  soundproof: number;
  city_view: number;
  twin_bed: number;
  non_smoking: number;
  available: boolean;
  availability_reason: string | null;
};
type Review = {
  review_id: string;
  name: string;
  country: string;
  score: number;
  title: string;
  body: string;
  stay: string;
};
type ActualHotel = {
  available: boolean; source?: string; retrieved_at?: string; place_id?: string;
  display_name?: string; formatted_address?: string; latitude?: number; longitude?: number;
  rating?: number; user_rating_count?: number; business_status?: string;
  property_type?: string; website_uri?: string; google_maps_uri?: string; reason?: string;
};
type CartItem = { id: string; hotel: H; room: R; searchId: string; conditions: any };
const DATASET_SCHEMAS: Record<string, Array<[string, string]>> = {
  HOTEL: [
    ["hotel_id", "호텔 아이디(PK)"], ["hotel_name", "호텔명"], ["city_name", "도시명"],
    ["grade", "등급"], ["hotel_address", "호텔 주소"], ["user_rating", "이용자 평점"],
    ["review_count", "리뷰 수"], ["property_type", "숙소 유형"],
    ["actual_address", "제공자료 실제 주소"], ["actual_city", "제공자료 도시"], ["actual_prefecture", "제공자료 도도부현"],
    ["actual_postal_code", "제공자료 우편번호"], ["actual_latitude", "제공자료 위도"], ["actual_longitude", "제공자료 경도"],
    ["actual_phone", "제공자료 전화번호"], ["actual_star_rating", "제공자료 성급"],
    ["supplier_hotel_code", "공급사 호텔 코드"], ["rtx_code", "RTX 코드"], ["agoda_code", "Agoda 코드"],
    ["expedia_code", "Expedia 코드"], ["top_selling_rank", "직전 월 판매 순위"],
    ["source_last_mapped_at", "원본 최종 매핑일"], ["actual_data_sources", "실제 정보 출처"],
  ],
  ROOM: [
    ["room_id", "객실 아이디(PK)"], ["hotel_id", "호텔 아이디(FK)"], ["guest_count", "투숙 인원"],
    ["room_count", "객실 수"], ["room_options", "객실 옵션"], ["pay_later_flag", "후결제 여부"],
    ["free_cancel_flag", "무료취소 여부"], ["room_price", "객실 가격"], ["room_type", "룸유형"],
  ],
  SEARCH: [
    ["search_id", "검색 아이디(PK)"], ["session_id", "세션 아이디"], ["search_time", "검색 시간"],
    ["query_text", "검색어"], ["checkin_date", "체크인 날짜"], ["checkout_date", "체크아웃 날짜"],
    ["total_result_count", "전체 검색 결과 수"], ["sort_option", "정렬 조건"],
    ["guest_count", "투숙 인원"], ["destination", "목적지(검색 지역)"],
  ],
  SEARCH_FILTER: [
    ["search_filter_id", "검색 필터 아이디(PK)"], ["search_id", "검색 아이디(FK)"],
    ["property_type", "숙소 유형"], ["property_grade", "숙소 등급"],
    ["user_rating_min", "최소 이용자 평점"], ["price", "최대 가격 범위"],
    ["amenity_count", "편의시설 선택수"], ["region", "지역"],
  ],
  USER: [
    ["user_id", "사용자 아이디(PK)"], ["user_name", "사용자명"], ["age_group", "연령대"],
    ["email", "이메일(UNIQUE)"], ["signup_at", "가입 시각"],
  ],
  EVENT: [
    ["event_id", "이벤트 아이디(PK)"], ["session_id", "세션 아이디"], ["event_type", "이벤트 유형"],
    ["event_at", "이벤트 발생 시각"], ["hotel_id", "호텔 아이디(FK)"],
    ["search_filter_id", "검색 필터 아이디(FK)"], ["search_id", "검색 아이디(FK)"],
    ["user_id", "사용자 아이디(FK)"], ["rating", "별점"],
    ["review_completed_at", "리뷰 작성 완료 시각"], ["review_text", "리뷰 텍스트"], ["device", "디바이스"],
  ],
  SEARCH_RESULT: [
    ["search_result_id", "검색 결과 아이디(PK)"], ["search_id", "검색 아이디(FK)"],
    ["hotel_id", "호텔 아이디(FK)"], ["room_id", "객실 아이디(FK)"],
    ["result_score", "검색결과 점수"], ["result_rank", "노출 순위"], ["price_rank", "가격 순위"],
  ],
  BOOKING: [
    ["booking_id", "예약 아이디(PK)"], ["user_id", "사용자 아이디(FK)"],
    ["hotel_id", "호텔 아이디(FK)"], ["room_id", "객실 아이디(FK)"],
    ["booking_status", "예약 상태"], ["booking_amount", "예약 금액"], ["booking_at", "예약 발생 시각"],
    ["checkin_date", "체크인 날짜"], ["checkout_date", "체크아웃 날짜"],
    ["guest_count", "투숙 인원"], ["room_count", "객실 수"], ["cancellation_deadline", "취소기한"],
  ],
};
for (const schema of Object.values(DATASET_SCHEMAS)) schema.push(["data_origin", "데이터 구분"]);
type S =
  | "profile"
  | "search"
  | "results"
  | "detail"
  | "booking"
  | "complete"
  | "wishlist"
  | "cart"
  | "admin";
const init: any = {
  city: "",
  subregion: "",
  keyword: "",
  checkin: "",
  checkout: "",
  guests: 2,
  rooms: 1,
  type: "",
  grade: "",
  rating: "",
  maxPrice: "",
  chain: "",
  sort: "rating",
  freeCancellation: false,
  payAtHotel: false,
  breakfast: false,
  familyRoom: false,
  petFriendly: false,
  pool: false,
  spa: false,
  balcony: false,
  bathtub: false,
  nonSmoking: false,
  cityView: false,
  twinBed: false,
  airConditioning: false,
  kitchen: false,
  washingMachine: false,
  soundproof: false,
  parking: false,
  restaurant: false,
  gym: false,
  laundry: false,
  airportShuttle: false,
  onsen: false,
  accessible: false,
  luggageStorage: false,
  frontDesk24h: false,
  nearStation: "",
};
async function api(body?: any, mode = "", adminCode = "") {
  const payload = body?.action === "event"
    ? { ...body, properties: { ...(body.properties || {}),
        device: /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent) ? "mobile" : "desktop" } }
    : body;
  return (
    await fetch(
      `/api/data${mode ? `?mode=${mode}` : ""}`,
      payload
        ? {
            method: "POST",
            headers: { "Content-Type": "application/json", ...(adminCode ? { "X-Admin-Code": adminCode } : {}) },
            body: JSON.stringify(payload),
          }
        : adminCode ? { headers: { "X-Admin-Code": adminCode } } : undefined,
    )
  ).json();
}
export default function Home() {
  const adminReturnScreen = useRef<S>("search");
  const adminCodeRef = useRef("");
  const collectionReturnScreen = useRef<S>("search");
  const [screen, setScreen] = useState<S>("profile"),
    [profileComplete, setProfileComplete] = useState(false),
    [profileError, setProfileError] = useState(""),
    [profile, setProfile] = useState({
      participantName: "",
      email: "",
      ageGroup: "",
      gender: "",
      travelFrequency: "",
      travelPurpose: "",
      companionType: "",
      consent: false,
    }),
    [c, setC] = useState<any>(init),
    [draftC, setDraftC] = useState<any>(init),
    [hotels, setHotels] = useState<H[]>([]),
    [hotel, setHotel] = useState<H | null>(null),
    [rooms, setRooms] = useState<R[]>([]),
    [detailReviews, setDetailReviews] = useState<Review[]>([]),
    [actualHotel, setActualHotel] = useState<ActualHotel | null>(null),
    [room, setRoom] = useState<R | null>(null),
    [searchId, setSearchId] = useState(""),
    [variant, setVariant] = useState(""),
    [reservation, setReservation] = useState(""),
    [admin, setAdmin] = useState<any>(),
    [adminTable, setAdminTable] = useState("HOTEL"),
    [adminQuery, setAdminQuery] = useState(""),
    [adminUser, setAdminUser] = useState(""),
    [trashTable, setTrashTable] = useState(""),
    [adminColumnFilters, setAdminColumnFilters] = useState<Record<string, string>>({}),
    [selectedAdmin, setSelectedAdmin] = useState(new Set<string>()),
    [busy, setBusy] = useState(false),
    [wishes, setWishes] = useState(new Set<string>()),
    [wishlistHotels, setWishlistHotels] = useState<H[]>([]),
    [cart, setCart] = useState<CartItem[]>([]),
    [galleryIndex, setGalleryIndex] = useState(0),
    [calendarMonth, setCalendarMonth] = useState("2026-09"),
    [pickingCheckout, setPickingCheckout] = useState(false);
  useEffect(() => {
    const seededConditions = {
      ...init,
      checkin: "2026-09-15",
      checkout: "2026-09-17",
    };
    setC(seededConditions);
    setDraftC(seededConditions);
    const savedProfile = sessionStorage.getItem("staytrace_participant");
    if (savedProfile) {
      try {
        const restored = JSON.parse(savedProfile);
        if (restored.participantName && restored.email) {
          setProfile(restored);
          setProfileComplete(true);
          setScreen("search");
        }
      } catch {
        sessionStorage.removeItem("staytrace_participant");
      }
    }
    try {
      const savedWishlist = JSON.parse(sessionStorage.getItem("staytrace_wishlist") || "[]") as H[];
      setWishlistHotels(savedWishlist);
      setWishes(new Set(savedWishlist.map((item) => item.id)));
      setCart(JSON.parse(sessionStorage.getItem("staytrace_cart") || "[]"));
    } catch {
      sessionStorage.removeItem("staytrace_wishlist");
      sessionStorage.removeItem("staytrace_cart");
    }
    api();
  }, []);
  const change = (k: string, v: any) => {
    setC((x: any) => ({
      ...x,
      [k]: v,
      ...(k === "city" ? { subregion: "" } : {}),
    }));
  };
  async function submitProfile(e: React.FormEvent) {
    e.preventDefault();
    if (
      !profile.participantName.trim() ||
      !profile.email.trim() ||
      !profile.ageGroup ||
      !profile.gender ||
      !profile.travelFrequency ||
      !profile.travelPurpose ||
      !profile.companionType ||
      !profile.consent
    ) {
      setProfileError("필요 정보를 입력 후 시작해 주세요.");
      return;
    }
    setProfileError("");
    setBusy(true);
    await api({
      action: "event",
      name: "participant_profile_submit",
      page: "profile",
      properties: {
        participant_name: profile.participantName.trim(),
        email: profile.email.trim().toLocaleLowerCase(),
        age_group: profile.ageGroup,
        gender: profile.gender,
        travel_frequency: profile.travelFrequency,
        travel_purpose: profile.travelPurpose,
        companion_type: profile.companionType,
        consent: true,
      },
    });
    sessionStorage.setItem("staytrace_participant", JSON.stringify(profile));
    setProfileComplete(true);
    setScreen("search");
    setBusy(false);
  }
  function liveChange(k: string, v: any) {
    setDraftC((current: any) => ({
      ...current,
      [k]: v,
      ...(k === "city" ? { subregion: "" } : {}),
    }));
  }
  async function applyFilters() {
    setBusy(true);
    const d = await api({
      action: "search",
      trigger: "filters_apply_button",
      conditions: draftC,
      parentId: searchId || null,
    });
    setC(draftC);
    setSearchId(d.searchId);
    setHotels(d.hotels);
    setBusy(false);
  }
  const nights = () =>
    Math.max(
      1,
      Math.round((+new Date(c.checkout) - +new Date(c.checkin)) / 86400000),
    );
  async function search() {
    setBusy(true);
    const d = await api({
      action: "search",
      trigger: "search_button",
      conditions: c,
      parentId: searchId || null,
    });
    setSearchId(d.searchId);
    setHotels(d.hotels);
    setDraftC(c);
    setScreen("results");
    setBusy(false);
  }
  async function detail(h: H) {
    await api({
      action: "event",
      name: "hotel_click",
      page: "results",
      searchId,
      hotelId: h.id,
    });
    await api({
      action: "event",
      name: "hotel_detail_view",
      page: "detail",
      searchId,
      hotelId: h.id,
    });
    const d = await api({
      action: "rooms",
      searchId,
      hotelId: h.id,
      conditions: c,
    });
    setHotel(h);
    setRooms(d.rooms);
    setActualHotel(d.actualHotel || null);
    setDetailReviews(d.reviews || []);
    setVariant(d.variant);
    setRoom(null);
    setGalleryIndex(0);
    setCalendarMonth(c.checkin.slice(0, 7));
    setPickingCheckout(false);
    setScreen("detail");
  }
  async function selectCalendarDate(date: string) {
    if (!hotel) return;
    let next: any;
    if (!pickingCheckout || date <= c.checkin) {
      const following = new Date(`${date}T00:00:00Z`);
      following.setUTCDate(following.getUTCDate() + 1);
      next = {
        ...c,
        checkin: date,
        checkout: following.toISOString().slice(0, 10),
      };
      setPickingCheckout(true);
    } else {
      next = { ...c, checkout: date };
      setPickingCheckout(false);
    }
    setC(next);
    setRoom(null);
    setBusy(true);
    await api({
      action: "event",
      name: "detail_calendar_change",
      page: "detail",
      searchId,
      hotelId: hotel.id,
      properties: {
        checkin: next.checkin,
        checkout: next.checkout,
        selection_stage: pickingCheckout ? "checkout" : "checkin",
      },
    });
    const d = await api({
      action: "rooms",
      searchId,
      hotelId: hotel.id,
      conditions: next,
    });
    setRooms(d.rooms);
    setDetailReviews(d.reviews || []);
    setVariant(d.variant);
    setBusy(false);
  }
  async function choose(r: R) {
    if (!r.available) return;
    setRoom(r);
    await api({
      action: "event",
      name: "room_select",
      page: "detail",
      searchId,
      hotelId: hotel?.id,
      properties: {
        room_id: r.id,
        spa_access: !!r.spa_access,
        requested_spa: !!c.spa,
        selected_options: {
          breakfast: !!r.breakfast,
          freeCancellation: !!r.free_cancellation,
          payAtHotel: !!r.pay_at_hotel,
          familyRoom: !!r.family_room,
          petFriendly: !!r.pet_friendly,
          pool: !!r.pool_access,
          spa: !!r.spa_access,
          balcony: !!r.balcony,
          bathtub: !!r.bathtub,
          nonSmoking: !!r.non_smoking,
          cityView: !!r.city_view,
          twinBed: !!r.twin_bed,
          airConditioning: !!r.air_conditioning,
          kitchen: !!r.kitchen,
          washingMachine: !!r.washing_machine,
          soundproof: !!r.soundproof,
        },
        variant,
      },
    });
  }
  async function start() {
    if (!room) return;
    await api({
      action: "event",
      name: "booking_start",
      page: "booking",
      searchId,
      hotelId: hotel?.id,
      properties: { room_id: room.id, variant },
    });
    setScreen("booking");
  }
  async function done() {
    if (!hotel || !room) return;
    const total = (hotel.price + room.price_modifier) * nights() * c.rooms,
      d = await api({
        action: "booking",
        searchId,
        hotelId: hotel.id,
        roomId: room.id,
        totalPrice: total,
        conditions: { checkin: c.checkin, checkout: c.checkout },
      });
    if (d.error === "room_unavailable") {
      setRoom(null);
      setScreen("detail");
      return;
    }
    setReservation(d.reservation);
    setScreen("complete");
  }
  async function cancel() {
    await api({
      action: "event",
      name: "booking_cancel",
      page: "booking",
      searchId,
      hotelId: hotel?.id,
      properties: { return_to: "room_selection", variant },
    });
    setScreen("detail");
  }
  async function goBack() {
    if (screen === "booking") return cancel();
    if (screen === "detail") {
      await api({
        action: "event",
        name: "back_to_results",
        page: "detail",
        searchId,
        hotelId: hotel?.id,
      });
      setScreen("results");
      return;
    }
    if (screen === "results") setScreen("search");
    else if (screen === "complete") setScreen("detail");
    else if (screen === "admin") setScreen(adminReturnScreen.current);
    else if (screen === "wishlist" || screen === "cart") setScreen(collectionReturnScreen.current);
    else setScreen("search");
  }
  async function openAdmin() {
    const adminCode = window.prompt("데이터 콘솔 지정 코드를 입력하세요.");
    if (adminCode === null) return;
    const data = await api(undefined, "admin", adminCode);
    if (data.error === "invalid_admin_code") {
      window.alert("데이터 콘솔 지정 코드가 올바르지 않습니다.");
      return;
    }
    adminCodeRef.current = adminCode;
    adminReturnScreen.current = screen === "admin" ? "search" : screen;
    setAdmin(data);
    setScreen("admin");
  }
  async function logout() {
    await api({
      action: "event",
      name: "participant_logout",
      page: screen,
      properties: { participant_name: profile.participantName.trim() },
    });
    sessionStorage.removeItem("staytrace_participant");
    sessionStorage.removeItem("staytrace_wishlist");
    sessionStorage.removeItem("staytrace_cart");
    setProfileComplete(false);
    setProfile({
      participantName: "",
      email: "",
      ageGroup: "",
      gender: "",
      travelFrequency: "",
      travelPurpose: "",
      companionType: "",
      consent: false,
    });
    setHotels([]);
    setHotel(null);
    setRoom(null);
    setWishes(new Set());
    setWishlistHotels([]);
    setCart([]);
    setScreen("profile");
  }
  async function refreshAdmin() {
    setBusy(true);
    setAdmin(await api(undefined, "admin", adminCodeRef.current));
    setBusy(false);
  }
  const csvText = (tableName: string, rows: any[]) => {
    if (!rows.length) return "";
    const columns = DATASET_SCHEMAS[tableName]?.map(([key]) => key) || Object.keys(rows[0]);
    const escape = (value: any) =>
      `"${String(value ?? "").replaceAll('"', '""')}"`;
    return [columns.map(escape).join(","), ...rows.map((row) =>
      columns.map((column) => escape(row[column])).join(","))].join("\r\n");
  };
  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob), link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  };
  function downloadCsv(tableName: string, rows: any[]) {
    const csv = csvText(tableName, rows);
    if (!csv) return;
    downloadBlob(
      new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" }),
      `${tableName.toLowerCase()}_${new Date(Date.now() + 9 * 3600000).toISOString().slice(0, 10)}.csv`,
    );
  }
  async function downloadAllCsv() {
    const tables = ["HOTEL", "ROOM", "SEARCH", "SEARCH_FILTER", "USER", "EVENT", "SEARCH_RESULT", "BOOKING"],
      date = new Date(Date.now() + 9 * 3600000).toISOString().slice(0, 10);
    for (const table of tables) {
      const csv = csvText(table, admin?.datasets?.[table] || []);
      if (!csv) continue;
      downloadBlob(
        new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" }),
        `${table.toLowerCase()}_${date}.csv`,
      );
      await new Promise((resolve) => window.setTimeout(resolve, 180));
    }
  }
  async function deleteAdminRow(table: string, row: any) {
    const idKey = `${table.toLowerCase()}_id`, rowId = row[idKey];
    if (!window.confirm(`${table}의 ${rowId} 데이터를 휴지통으로 이동할까요?`)) return;
    if (!window.confirm(`최종 확인: ${rowId} 데이터를 정말 삭제하시겠습니까? 복구 전까지 콘솔에서 표시되지 않습니다.`)) return;
    await api({ action: "admin_delete", table, rowId }, "", adminCodeRef.current);
    await refreshAdmin();
  }
  async function restoreAdminRow(table: string, rowId: string) {
    await api({ action: "admin_restore", table, rowId }, "", adminCodeRef.current);
    await refreshAdmin();
  }
  const adminRowId = (table: string, row: any) =>
    String(row[`${table.toLowerCase()}_id`] || "");
  const adminSelectionKey = (table: string, rowId: string) => `${table}:${rowId}`;
  function toggleAdminSelection(table: string, rowId: string) {
    setSelectedAdmin((current) => {
      const next = new Set(current), key = adminSelectionKey(table, rowId);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }
  async function bulkDeleteAdmin(items: Array<{ table: string; rowId: string }>) {
    if (!items.length || !window.confirm(`선택한 ${items.length}개 자료를 휴지통으로 이동할까요?`)) return;
    if (!window.confirm(`최종 확인: ${items.length}개 자료를 정말 삭제하시겠습니까? 복구 전까지 콘솔에서 표시되지 않습니다.`)) return;
    setBusy(true);
    await api({ action: "admin_bulk_delete", items }, "", adminCodeRef.current);
    setSelectedAdmin(new Set());
    await refreshAdmin();
  }
  async function bulkRestoreAdmin(items: Array<{ table: string; rowId: string }>) {
    if (!items.length) return;
    setBusy(true);
    await api({ action: "admin_bulk_restore", items }, "", adminCodeRef.current);
    setSelectedAdmin(new Set());
    await refreshAdmin();
  }
  async function wish(h: H) {
    const n = new Set(wishes),
      on = n.has(h.id);
    on ? n.delete(h.id) : n.add(h.id);
    setWishes(n);
    const nextHotels = on
      ? wishlistHotels.filter((item) => item.id !== h.id)
      : [...wishlistHotels.filter((item) => item.id !== h.id), h];
    setWishlistHotels(nextHotels);
    sessionStorage.setItem("staytrace_wishlist", JSON.stringify(nextHotels));
    await api({
      action: "event",
      name: on ? "wishlist_remove" : "wishlist_add",
      page: screen,
      searchId,
      hotelId: h.id,
    });
  }
  async function openCollection(target: "wishlist" | "cart") {
    collectionReturnScreen.current = ["wishlist", "cart", "admin", "profile"].includes(screen) ? "search" : screen;
    setScreen(target);
    await api({
      action: "event", name: target === "wishlist" ? "wishlist_view" : "cart_view",
      page: target, searchId,
      properties: { item_count: target === "wishlist" ? wishlistHotels.length : cart.length },
    });
  }
  async function toggleCart(h: H, r: R) {
    const itemId = `${h.id}:${r.id}:${c.checkin}:${c.checkout}`,
      exists = cart.some((item) => item.id === itemId),
      next = exists ? cart.filter((item) => item.id !== itemId) :
        [...cart, { id: itemId, hotel: h, room: r, searchId, conditions: { ...c } }];
    setCart(next);
    sessionStorage.setItem("staytrace_cart", JSON.stringify(next));
    await api({
      action: "event", name: exists ? "cart_remove" : "cart_add", page: screen,
      searchId, hotelId: h.id,
      properties: { room_id: r.id, checkin: c.checkin, checkout: c.checkout },
    });
  }
  async function bookCartItem(item: CartItem) {
    setHotel(item.hotel); setRoom(item.room); setC(item.conditions); setDraftC(item.conditions);
    setSearchId(item.searchId); setScreen("booking");
    await api({ action: "event", name: "cart_booking_start", page: "cart",
      searchId: item.searchId, hotelId: item.hotel.id, properties: { room_id: item.room.id } });
    await api({ action: "event", name: "booking_start", page: "booking",
      searchId: item.searchId, hotelId: item.hotel.id,
      properties: { room_id: item.room.id, source: "cart" } });
  }
  async function removeCartItem(item: CartItem) {
    const next = cart.filter((entry) => entry.id !== item.id);
    setCart(next); sessionStorage.setItem("staytrace_cart", JSON.stringify(next));
    await api({ action: "event", name: "cart_remove", page: "cart",
      searchId: item.searchId, hotelId: item.hotel.id, properties: { room_id: item.room.id } });
  }
  async function showGalleryImage(index: number, method: "arrow" | "thumbnail") {
    setGalleryIndex(index);
    if (!hotel) return;
    await api({
      action: "event",
      name: "hotel_gallery_view",
      page: "detail",
      searchId,
      hotelId: hotel.id,
      properties: { image_index: index + 1, method },
    });
  }
  const imagePaths = [
      "/hotel-images/exterior.webp",
      "/hotel-images/room.webp",
      "/hotel-images/lobby.webp",
      "/hotel-images/onsen.webp",
      "/hotel-images/pool.webp",
      "/hotel-images/breakfast.webp",
      "/hotel-images/ryokan-room.webp",
      "/hotel-images/rooftop.webp",
    ],
    representativeImage = (h: H) => {
      if (h.type === "Ryokan") return "/hotel-images/ryokan-room.webp";
      if (h.onsen || h.spa) return "/hotel-images/onsen.webp";
      if (h.pool) return "/hotel-images/pool.webp";
      if (h.balcony) return "/hotel-images/rooftop.webp";
      if (h.breakfast) return "/hotel-images/breakfast.webp";
      const hash = [...h.name].reduce((sum, char) => sum + char.charCodeAt(0), 0);
      return ["/hotel-images/exterior.webp", "/hotel-images/room.webp", "/hotel-images/lobby.webp"][hash % 3];
    },
    galleryImages = (h: H) => {
      const representative = representativeImage(h);
      return [representative, ...imagePaths.filter((path) => path !== representative)];
    },
    hotelDescription = (h: H) =>
      `${h.city} ${h.subregion}에 자리한 ${h.type === "Ryokan" ? "일본식 료칸" : h.type === "Resort" ? "휴양형 리조트" : "도심형 숙소"}입니다. 역에서 약 ${h.station_distance}m 거리에 있으며 ${[
        h.spa && "스파",
        h.onsen && "온천",
        h.pool && "수영장",
        h.breakfast && "조식",
        h.restaurant && "레스토랑",
        h.luggage_storage && "짐 보관",
      ].filter(Boolean).slice(0, 3).join("·") || "무료 Wi-Fi와 기본 편의시설"}을 이용할 수 있습니다. 객실별 포함 조건은 상품 선택 단계에서 다시 확인하세요.`;
  const monthDate = new Date(`${calendarMonth}-01T00:00:00Z`),
    monthYear = monthDate.getUTCFullYear(),
    monthIndex = monthDate.getUTCMonth(),
    monthDays = new Date(Date.UTC(monthYear, monthIndex + 1, 0)).getUTCDate(),
    monthOffset = monthDate.getUTCDay(),
    calendarCells = [
      ...Array.from({ length: monthOffset }, () => null),
      ...Array.from({ length: monthDays }, (_, i) => {
        const day = String(i + 1).padStart(2, "0");
        return `${calendarMonth}-${day}`;
      }),
    ],
    reviewItems = detailReviews;
  const activeAdminRows = adminTable === "TRASH" ? [] : (admin?.datasets?.[adminTable] || []),
    datasetColumns = DATASET_SCHEMAS[adminTable] || [],
    filteredAdminRows = activeAdminRows.filter((row: any) => {
      const rowId = adminRowId(adminTable, row),
        owner = admin?.ownership?.[adminTable]?.[rowId] || "",
        textMatch = !adminQuery || JSON.stringify(row).toLocaleLowerCase().includes(adminQuery.toLocaleLowerCase()),
        columnMatch = Object.entries(adminColumnFilters).every(([column, value]) =>
          !value || String(row[column] ?? "").toLocaleLowerCase().includes(value.toLocaleLowerCase()));
      return textMatch && columnMatch && (!adminUser || owner === adminUser);
    }),
    filteredDeletedRows = (admin?.deleted || []).filter((row: any) => {
      const textMatch = !adminQuery || JSON.stringify(row).toLocaleLowerCase().includes(adminQuery.toLocaleLowerCase()),
        columnMatch = Object.entries(adminColumnFilters).every(([column, value]) =>
          !value || String(row[column] ?? "").toLocaleLowerCase().includes(value.toLocaleLowerCase()));
      return textMatch && columnMatch && (!trashTable || row.table_name === trashTable) &&
        (!adminUser || row.owner_user_id === adminUser);
    }),
    journeyEvents = (admin?.datasets?.EVENT || []).filter((event: any) =>
      (!adminUser || event.user_id === adminUser) &&
      (!adminQuery || JSON.stringify(event).toLocaleLowerCase().includes(adminQuery.toLocaleLowerCase()))),
    journeySessions = Object.values(journeyEvents.reduce((groups: Record<string, any>, event: any) => {
      const key = event.session_id || "세션 없음";
      if (!groups[key]) groups[key] = { sessionId: key, userId: event.user_id, events: [] };
      groups[key].events.push(event);
      return groups;
    }, {})).map((session: any) => ({
      ...session,
      events: session.events.sort((a: any, b: any) => String(a.event_at).localeCompare(String(b.event_at))),
    })).sort((a: any, b: any) =>
      String(b.events[b.events.length - 1]?.event_at || "").localeCompare(String(a.events[a.events.length - 1]?.event_at || ""))),
    visibleSelectionKeys = adminTable === "TRASH"
      ? filteredDeletedRows.map((row: any) => adminSelectionKey(row.table_name, row.row_id))
      : filteredAdminRows.map((row: any) => adminSelectionKey(adminTable, adminRowId(adminTable, row))),
    allVisibleSelected = visibleSelectionKeys.length > 0 &&
      visibleSelectionKeys.every((key: string) => selectedAdmin.has(key));
  function toggleAllVisible() {
    setSelectedAdmin((current) => {
      const next = new Set(current);
      for (const key of visibleSelectionKeys) allVisibleSelected ? next.delete(key) : next.add(key);
      return next;
    });
  }
  function setColumnFilter(column: string, value: string) {
    setAdminColumnFilters((current) => ({ ...current, [column]: value }));
    setSelectedAdmin(new Set());
  }
  const field = (l: string, k: string, t = "text") => (
      <label>
        {l}
        <input
          type={t}
          value={c[k]}
          min={t === "date" ? "2026-01-01" : undefined}
          max={t === "date" ? "2026-12-31" : undefined}
          onChange={(e) => change(k, e.target.value)}
        />
      </label>
    ),
    select = (l: string, k: string, a: string[]) => (
      <label>
        {l}
        <select value={c[k]} onChange={(e) => change(k, e.target.value)}>
          {a.map((x) => (
            <option key={x} value={x}>
              {x || (k === "city" ? "지역 선택 안 함" : "전체")}
            </option>
          ))}
        </select>
      </label>
    );
  return (
    <>
      <header>
        <button
          className="brand"
          onClick={() => setScreen(profileComplete ? "search" : "profile")}
        >
          StayTrace
        </button>
        <nav>
          {profileComplete && (
            <div className="loginStatus" title="현재 브라우저 창에서 로그인 상태가 유지됩니다">
              <span />
              <p><b>로그인 중</b><small>{profile.participantName}님</small></p>
              <button onClick={logout}>로그아웃</button>
            </div>
          )}
          <button
            onClick={() => setScreen(profileComplete ? "search" : "profile")}
          >
            호텔 찾기
          </button>
          {profileComplete && <button onClick={() => void openCollection("wishlist")}>찜 목록 <b>{wishlistHotels.length}</b></button>}
          {profileComplete && <button onClick={() => void openCollection("cart")}>장바구니 <b>{cart.length}</b></button>}
          <button onClick={openAdmin}>데이터 콘솔</button>
        </nav>
      </header>
      {["results", "detail", "booking", "complete", "wishlist", "cart", "admin"].includes(screen) && (
        <button className="persistentBackButton" onClick={goBack} aria-label="이전 화면으로 돌아가기">
          <span aria-hidden="true">←</span> 이전 화면
        </button>
      )}
      <main>
        {screen === "profile" && (
          <section className="profileGate">
            <div className="profileWelcome">
              <span>STAYTRACE PARTICIPANT</span>
              <h1>여행 검색을 시작하기 전에</h1>
              <p>
                검색 효율과 예약 행동을 분석하고 사용자를 구분하기 위해 필요한
                최소한의 정보만 수집합니다. 입력 정보는 연구용 세션과 행동 로그를
                연결하는 목적으로만 사용됩니다.
              </p>
              <h2 className="participationTitle">참여 과정</h2>
              <ol className="participationSteps">
                <li>참여자 정보 입력</li>
                <li>원하는 조건으로 호텔 검색</li>
                <li>상세 옵션 확인 및 객실 선택</li>
                <li>예약 과정까지 완료</li>
              </ol>
              <p className="rewardNotice">
                유효한 이메일을 입력하고 예약 과정까지 완료한 참여자에게
                1인당 츄파춥스 1개 기프티콘을 제공합니다.
              </p>
            </div>
            <form className="profileForm" onSubmit={submitProfile} noValidate>
              <div className="formTitle">
                <span>PARTICIPANT SIGN IN</span>
                <h2>참여자 정보 입력</h2>
              </div>
              <label>
                이름 *
                <input
                  required
                  maxLength={30}
                  placeholder="이름을 입력하세요"
                  value={profile.participantName}
                  onChange={(e) =>
                    setProfile({ ...profile, participantName: e.target.value })
                  }
                />
              </label>
              <label>
                이메일 *
                <input
                  required
                  type="email"
                  maxLength={120}
                  placeholder="이메일을 입력하세요"
                  value={profile.email}
                  onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                />
              </label>
              <div className="profileGrid">
                <label>
                  연령대 *
                  <select
                    required
                    value={profile.ageGroup}
                    onChange={(e) =>
                      setProfile({ ...profile, ageGroup: e.target.value })
                    }
                  >
                    <option value="">선택</option>
                    {["10대", "20대", "30대", "40대", "50대", "60대 이상"].map(
                      (x) => (
                        <option key={x}>{x}</option>
                      ),
                    )}
                  </select>
                </label>
                <label>
                  성별 *
                  <select
                    required
                    value={profile.gender}
                    onChange={(e) =>
                      setProfile({ ...profile, gender: e.target.value })
                    }
                  >
                    <option value="">선택</option>
                    <option>여성</option>
                    <option>남성</option>
                    <option>기타</option>
                  </select>
                </label>
              </div>
              <label>
                연간 여행 빈도 *
                <select
                  required
                  value={profile.travelFrequency}
                  onChange={(e) =>
                    setProfile({ ...profile, travelFrequency: e.target.value })
                  }
                >
                  <option value="">선택</option>
                  <option>연 1회 이하</option>
                  <option>연 2~3회</option>
                  <option>연 4~6회</option>
                  <option>연 7회 이상</option>
                </select>
              </label>
              <div className="profileGrid">
                <label>
                  이번 여행 목적 *
                  <select
                    required
                    value={profile.travelPurpose}
                    onChange={(e) =>
                      setProfile({ ...profile, travelPurpose: e.target.value })
                    }
                  >
                    <option value="">선택</option>
                    <option>휴가·관광</option>
                    <option>출장</option>
                    <option>가족 방문</option>
                    <option>기념일</option>
                    <option>기타</option>
                  </select>
                </label>
                <label>
                  동행 유형 *
                  <select
                    required
                    value={profile.companionType}
                    onChange={(e) =>
                      setProfile({ ...profile, companionType: e.target.value })
                    }
                  >
                    <option value="">선택</option>
                    <option>혼자</option>
                    <option>커플</option>
                    <option>친구</option>
                    <option>가족</option>
                    <option>직장 동료</option>
                  </select>
                </label>
              </div>
              <label className="consentCheck">
                <input
                  type="checkbox"
                  checked={profile.consent}
                  onChange={(e) =>
                    setProfile({ ...profile, consent: e.target.checked })
                  }
                />
                연구 목적으로 검색 및 예약 행동 로그를 수집하는 데 동의합니다. *
              </label>
              {profileError && <p className="profileError" role="alert">{profileError}</p>}
              <button
                className="primaryBtn"
                type="submit"
                disabled={busy}
              >
                {busy ? "정보 저장 중…" : "호텔 검색 시작 →"}
              </button>
            </form>
          </section>
        )}
        {screen === "search" && (
          <>
            <section className="hero">
              <span>JAPAN STAYS</span>
              <h1>어디로 떠나시나요?</h1>
              <p>호텔명이나 지역과 기본 여행 일정만 입력해 빠르게 찾아보세요.</p>
            </section>
            <section className="searchPanel">
              <label className="keywordField">
                호텔명 또는 지역 검색
                <input
                  value={c.keyword}
                  placeholder="예: 신주쿠, 하얏트, 삿포로 스파"
                  onChange={(e) => change("keyword", e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && search()}
                />
              </label>
              <div className="primary">
                {select("목적지", "city", [
                  "",
                  "Tokyo",
                  "Osaka",
                  "Kyoto",
                  "Fukuoka",
                  "Sapporo",
                ])}
                <label>
                  세부지역
                  <select
                    value={c.subregion}
                    disabled={!c.city}
                    onChange={(e) => change("subregion", e.target.value)}
                  >
                    <option value="">{c.city ? "전체 세부지역" : "목적지를 먼저 선택하세요"}</option>
                    {(HOTEL_SUBREGIONS[c.city] || []).map((area) => (
                      <option key={area} value={area}>{area}</option>
                    ))}
                  </select>
                </label>
                {field("체크인", "checkin", "date")}
                {field("체크아웃", "checkout", "date")}
                {field("인원", "guests", "number")}
                {field("객실", "rooms", "number")}
              </div>
              <button className="primaryBtn" onClick={search} disabled={busy}>
                {busy ? "검색 중…" : "검색하기 →"}
              </button>
            </section>
          </>
        )}
        {screen === "results" && (
          <>
            <section className="top">
              <div>
                <span>{[c.city || "일본 전 지역", c.subregion].filter(Boolean).join(" · ")}</span>
                <h1>숙소 {hotels.length}곳</h1>
                <p>
                  {c.keyword && `“${c.keyword}” 검색 · `}
                  {c.checkin} — {c.checkout} · {c.guests}명
                </p>
              </div>
              <button onClick={() => setScreen("search")}>조건 수정</button>
            </section>
            <section className="resultsSearchEngine" aria-label="결과 내 검색">
              <label>
                호텔명 또는 지역 검색
                <input
                  value={draftC.keyword}
                  placeholder="호텔명·지역 검색"
                  onChange={(e) => liveChange("keyword", e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && applyFilters()}
                />
              </label>
              <label>
                목적지
                <select value={draftC.city} onChange={(e) => liveChange("city", e.target.value)}>
                  {["", "Tokyo", "Osaka", "Kyoto", "Fukuoka", "Sapporo"].map((city) => (
                    <option key={city} value={city}>{city || "지역 선택 안 함"}</option>
                  ))}
                </select>
              </label>
              <label>
                세부지역
                <select
                  value={draftC.subregion}
                  disabled={!draftC.city}
                  onChange={(e) => liveChange("subregion", e.target.value)}
                >
                  <option value="">{draftC.city ? "전체 세부지역" : "목적지 먼저 선택"}</option>
                  {(HOTEL_SUBREGIONS[draftC.city] || []).map((area) => (
                    <option key={area} value={area}>{area}</option>
                  ))}
                </select>
              </label>
              <button className="primaryBtn" onClick={applyFilters} disabled={busy}>
                {busy ? "검색 중…" : "검색"}
              </button>
            </section>
            <div className="resultsLayout">
              <aside className="liveFilters">
                <div className="filterHeading">
                  <div>
                    <span>APPLY FILTERS</span>
                    <h2>상세 옵션</h2>
                  </div>
                  {busy && <small>결과 갱신 중…</small>}
                </div>
                <label>
                  최대 1박 가격
                  <select
                    value={draftC.maxPrice}
                    onChange={(e) => liveChange("maxPrice", e.target.value)}
                  >
                    <option value="">가격 제한 없음</option>
                    <option value="50000">5만원 이하</option>
                    <option value="100000">10만원 이하</option>
                    <option value="150000">15만원 이하</option>
                    <option value="200000">20만원 이하</option>
                    <option value="250000">25만원 이하</option>
                    <option value="300000">30만원 이하</option>
                    <option value="400000">40만원 이하</option>
                    <option value="500000">50만원 이하</option>
                  </select>
                </label>
                <label>
                  최소 이용자 평점
                  <select
                    value={draftC.rating}
                    onChange={(e) => liveChange("rating", e.target.value)}
                  >
                    <option value="">전체</option>
                    <option value="7">7점 이상</option>
                    <option value="8">8점 이상</option>
                    <option value="9">9점 이상</option>
                  </select>
                </label>
                <label>
                  정렬
                  <select
                    value={draftC.sort}
                    onChange={(e) => liveChange("sort", e.target.value)}
                  >
                    <option value="rating">별점 높은 순</option>
                    <option value="reviews">리뷰 많은 순</option>
                    <option value="price">가격 낮은 순</option>
                    <option value="price_high">가격 높은 순</option>
                  </select>
                </label>
                <label>
                  역에서 최대 거리
                  <select
                    value={draftC.nearStation}
                    onChange={(e) => liveChange("nearStation", e.target.value)}
                  >
                    <option value="">제한 없음</option>
                    <option value="300">300m 이내</option>
                    <option value="500">500m 이내</option>
                    <option value="1000">1km 이내</option>
                  </select>
                </label>
                <h3>예약 정책과 시설</h3>
                <div className="liveChecks">
                  {[
                    ["freeCancellation", "무료 취소"],
                    ["payAtHotel", "현장 결제"],
                    ["breakfast", "조식 포함"],
                    ["familyRoom", "가족 객실"],
                    ["petFriendly", "반려동물"],
                    ["pool", "수영장"],
                    ["spa", "스파"],
                    ["balcony", "발코니"],
                    ["bathtub", "욕조"],
                    ["nonSmoking", "금연"],
                    ["cityView", "시티뷰"],
                    ["twinBed", "트윈베드"],
                    ["airConditioning", "에어컨"],
                    ["kitchen", "주방"],
                    ["washingMachine", "세탁기"],
                    ["soundproof", "방음"],
                    ["parking", "주차장"],
                    ["restaurant", "레스토랑"],
                    ["gym", "피트니스"],
                    ["laundry", "세탁 시설"],
                    ["airportShuttle", "공항 셔틀"],
                    ["onsen", "온천"],
                    ["accessible", "장애인 편의"],
                    ["luggageStorage", "짐 보관"],
                    ["frontDesk24h", "24시간 프런트"],
                  ].map(([key, label]) => (
                    <label key={key}>
                      <input
                        type="checkbox"
                        checked={draftC[key]}
                        onChange={(e) => liveChange(key, e.target.checked)}
                      />
                      <span>{label}</span>
                    </label>
                  ))}
                </div>
                <button
                  className="clearFilters"
                  onClick={() => {
                    const reset = {
                      ...draftC,
                      keyword: "",
                      subregion: "",
                      grade: "",
                      rating: "",
                      maxPrice: "",
                      sort: "rating",
                      freeCancellation: false,
                      payAtHotel: false,
                      breakfast: false,
                      familyRoom: false,
                      petFriendly: false,
                      pool: false,
                      spa: false,
                      balcony: false,
                      bathtub: false,
                      nonSmoking: false,
                      cityView: false,
                      twinBed: false,
                      airConditioning: false,
                      kitchen: false,
                      washingMachine: false,
                      soundproof: false,
                      parking: false,
                      restaurant: false,
                      gym: false,
                      laundry: false,
                      airportShuttle: false,
                      onsen: false,
                      accessible: false,
                      luggageStorage: false,
                      frontDesk24h: false,
                      nearStation: "",
                    };
                    setDraftC(reset);
                  }}
                >
                  옵션 초기화
                </button>
                <button className="primaryBtn applyFilters" onClick={applyFilters} disabled={busy}>
                  {busy ? "적용 중…" : "선택 옵션 적용"}
                </button>
                <p className="filterApplyNote">옵션은 위 버튼을 눌렀을 때 결과와 행동 로그에 반영됩니다.</p>
              </aside>
              <div className={`cards resultCards ${busy ? "updating" : ""}`}>
                {hotels.map((h) => (
                  <article
                    className="card clickableCard"
                    key={h.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => detail(h)}
                    onKeyDown={(e) => {
                      if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " "))
                        void detail(h);
                    }}
                    aria-label={`${h.name} 상품 페이지 열기`}
                  >
                    <div
                      className="photo"
                      style={{
                        backgroundImage: `url(${representativeImage(h)})`,
                      }}
                    />
                    <div className="cardBody">
                      <small className="cardDataOrigin">
                        {h.actual_data_available ? "호텔 기본정보: 사용자 제공 실제 자료 · 가격·평점·시설: 가상" : "호텔명·도시: 공개자료 참고 · 가격·평점·시설: 가상"}
                      </small>
                      <span>{h.type}</span>
                      <h2>{h.name}</h2>
                      <p>
                        {h.city} · {h.subregion} · {h.chain || "독립 숙소"}<br />
                        {h.actual_address ? <>제공자료 주소: {h.actual_address}<br /></> : null}
                        역에서 {h.station_distance}m
                      </p>
                      <div className="badges">
                        {h.free_cancellation ? <b>무료 취소</b> : null}
                        {h.pay_at_hotel ? <b>현장 결제</b> : null}
                        {h.breakfast ? <b>조식</b> : null}
                        {h.spa ? <b>스파</b> : null}
                        {h.balcony ? <b>발코니</b> : null}
                      </div>
                      <div className="price">
                        <strong>{h.price.toLocaleString()}원~</strong>
                        <em>
                          평점 {h.rating.toFixed(1)} · 리뷰{" "}
                          {h.reviews.toLocaleString()}개
                        </em>
                      </div>
                      <div className="actions">
                        <button onClick={(e) => { e.stopPropagation(); void wish(h); }}>
                          {wishes.has(h.id) ? "♥ 찜됨" : "♡ 찜"}
                        </button>
                        <button className="solid" onClick={(e) => { e.stopPropagation(); void detail(h); }}>
                          객실 보기
                        </button>
                      </div>
                    </div>
                  </article>
                ))}
                {!busy && hotels.length === 0 && (
                  <div className="emptyResults">
                    <h2>조건에 맞는 숙소가 없습니다</h2>
                    <p>왼쪽 옵션을 줄이면 결과가 바로 다시 표시됩니다.</p>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
        {screen === "wishlist" && (
          <section className="collectionPage">
            <div className="collectionHeading">
              <span>SAVED STAYS</span><h1>찜한 숙소</h1>
              <p>비교하고 싶은 숙소를 한곳에서 다시 확인하세요.</p>
            </div>
            <div className="collectionGrid">
              {wishlistHotels.map((h) => (
                <article className="collectionCard" key={h.id}>
                  <div className="collectionPhoto" style={{ backgroundImage: `url(${representativeImage(h)})` }} />
                  <div><span>{h.city} · {h.subregion}</span><h2>{h.name}</h2>
                    <p>평점 {h.rating.toFixed(1)} · 리뷰 {h.reviews.toLocaleString()}개</p>
                    <strong>{h.price.toLocaleString()}원~</strong>
                    <div className="actions"><button onClick={() => void wish(h)}>찜 삭제</button>
                      <button className="solid" onClick={() => void detail(h)}>객실 보기</button></div>
                  </div>
                </article>
              ))}
            </div>
            {!wishlistHotels.length && <div className="emptyResults"><h2>찜한 숙소가 없습니다</h2><p>검색 결과에서 ♡ 찜 버튼을 눌러 추가하세요.</p></div>}
          </section>
        )}
        {screen === "cart" && (
          <section className="collectionPage">
            <div className="collectionHeading">
              <span>ROOM CART</span><h1>장바구니</h1>
              <p>선택한 날짜와 객실 상품을 확인하고 예약 단계로 이동하세요.</p>
            </div>
            <div className="cartList">
              {cart.map((item) => (
                <article className="cartItem" key={item.id}>
                  <div className="collectionPhoto" style={{ backgroundImage: `url(${representativeImage(item.hotel)})` }} />
                  <div><span>{item.hotel.city} · {item.hotel.subregion}</span><h2>{item.hotel.name}</h2>
                    <h3>{item.room.name}</h3><p>{item.conditions.checkin} — {item.conditions.checkout} · {item.conditions.guests}명</p>
                    <p>{item.room.bed_type} · {item.room.view_type} · 최대 {item.room.capacity}명</p></div>
                  <div className="cartPrice"><strong>{(item.hotel.price + item.room.price_modifier).toLocaleString()}원 / 1박</strong>
                    <button onClick={() => void removeCartItem(item)}>삭제</button>
                    <button className="solid" onClick={() => void bookCartItem(item)}>예약 진행</button></div>
                </article>
              ))}
            </div>
            {!cart.length && <div className="emptyResults"><h2>장바구니가 비어 있습니다</h2><p>호텔 상세에서 원하는 객실을 장바구니에 담아보세요.</p></div>}
          </section>
        )}
        {screen === "detail" && hotel && (
          <>
            <section className="detail">
              <div className="propertyGallery">
                <div
                  className="detailPhoto"
                  style={{ backgroundImage: `url(${galleryImages(hotel)[galleryIndex]})` }}
                  role="img"
                  aria-label={`${hotel.name} 시설 이미지 ${galleryIndex + 1}`}
                >
                  <button
                    className="galleryArrow galleryPrev"
                    onClick={() => void showGalleryImage((galleryIndex + 7) % 8, "arrow")}
                    aria-label="이전 이미지"
                  >←</button>
                  <span className="galleryCounter">{galleryIndex + 1} / 8</span>
                  <button
                    className="galleryArrow galleryNext"
                    onClick={() => void showGalleryImage((galleryIndex + 1) % 8, "arrow")}
                    aria-label="다음 이미지"
                  >→</button>
                </div>
                <div className="galleryThumbs" aria-label="숙소 이미지 썸네일">
                  {galleryImages(hotel).map((path, index) => (
                    <button
                      key={path}
                      className={index === galleryIndex ? "active" : ""}
                      onClick={() => void showGalleryImage(index, "thumbnail")}
                      aria-label={`${index + 1}번 이미지 보기`}
                    >
                      <img src={path} alt="" />
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <span>
                  {hotel.city} · {hotel.subregion} · {hotel.type}
                </span>
                <h1>{hotel.name}</h1>
                {hotel.actual_data_available ? (
                  <div className="actualHotelFacts">
                    <div className="dataOriginHeading"><b>제공 자료 기반 실제 정보</b><small>{hotel.actual_data_sources}</small></div>
                    <p>{hotel.actual_address || [hotel.actual_city, hotel.actual_prefecture].filter(Boolean).join(", ")}</p>
                    <ul>
                      {hotel.actual_star_rating !== "" && <li>제공자료 성급 {hotel.actual_star_rating} / 5</li>}
                      {hotel.actual_phone && <li>전화 {hotel.actual_phone}</li>}
                      {hotel.supplier_hotel_code && <li>공급사 코드 {hotel.supplier_hotel_code}</li>}
                      {hotel.agoda_code && <li>Agoda 코드 {hotel.agoda_code}</li>}
                    </ul>
                  </div>
                ) : null}
                {actualHotel?.available ? (
                  <div className="actualHotelFacts">
                    <div className="dataOriginHeading"><b>실제 확인 정보</b><small>{actualHotel.source}</small></div>
                    <h2>{actualHotel.display_name}</h2>
                    <p>{actualHotel.formatted_address}</p>
                    <ul>
                      {actualHotel.rating ? <li>실제 플랫폼 평점 {actualHotel.rating} / 5 · 평가 {actualHotel.user_rating_count?.toLocaleString?.() || "정보 없음"}개</li> : <li>실제 평점·평가 수는 현재 출처에서 제공되지 않음</li>}
                      <li>숙소 유형 {actualHotel.property_type || "정보 없음"}</li>
                      <li>운영 상태 {actualHotel.business_status === "OPERATIONAL" ? "영업 중" : actualHotel.business_status || "정보 없음"}</li>
                    </ul>
                    <div className="actualLinks">
                      {actualHotel.website_uri && <a href={actualHotel.website_uri} target="_blank" rel="noreferrer">공식 웹사이트</a>}
                      {actualHotel.google_maps_uri && <a href={actualHotel.google_maps_uri} target="_blank" rel="noreferrer">원본 지도에서 확인</a>}
                    </div>
                  </div>
                ) : (
                  <p className="actualUnavailable">실제 정보 조회 결과 없음 · 아래 정보는 연구용 가상 데이터입니다.</p>
                )}
                <div className="simulatedRating">
                  <strong>{hotel.rating.toFixed(1)} / 10</strong>
                  <span>리뷰 {hotel.reviews.toLocaleString()}개</span>
                  <small>가상 데이터 · 연구용 시뮬레이션 평점·리뷰 수</small>
                </div>
                <p><b className="virtualBadge">가상</b> 숙소 공용시설: {JSON.parse(hotel.amenities).join(" · ")}</p>
                <div className="propertyIntroduction">
                  <h2>숙소 소개</h2>
                  <p>{hotelDescription(hotel)}</p>
                </div>
                <p className="dataNote">
                  위 실제 확인 정보는 상세 진입 시 Google Places에서 실시간 조회하며 장기 저장하지 않습니다.
                  호텔 목록의 이름과 도시는 공개 숙박업소 자료를 참고했지만 개별 검증 전에는 참고값입니다.
                  이미지·세부지역·거리·등급·가격·객실·시설·재고·예약 정책은 연구용 가상 데이터입니다.
                </p>
                <ul>
                  <li>역에서 {hotel.station_distance}m</li>
                  <li>
                    {hotel.free_cancellation
                      ? "무료 취소 상품 있음"
                      : "취소 수수료 적용"}
                  </li>
                  <li>
                    {hotel.pay_at_hotel
                      ? "현장 결제 상품 있음"
                      : "예약 시 결제"}
                  </li>
                </ul>
              </div>
            </section>
            <section className="hotelOptions">
              <div className="optionIntro">
                <span>PROPERTY DETAILS</span>
                <h2>숙소 편의시설과 이용 조건</h2>
                <p>숙소 공용시설과 객실별 제공 옵션은 서로 다를 수 있습니다.</p>
              </div>
              <div className="optionGroups">
                <article>
                  <h3>편의시설</h3>
                  <ul>
                    <li>✓ 무료 Wi-Fi</li>
                    <li>{hotel.restaurant ? "✓" : "–"} 레스토랑</li>
                    <li>{hotel.gym ? "✓" : "–"} 피트니스 센터</li>
                    <li>{hotel.laundry ? "✓" : "–"} 세탁 시설</li>
                    <li>{hotel.pool ? "✓" : "–"} 수영장</li>
                    <li>{hotel.spa ? "✓" : "–"} 스파</li>
                    <li>{hotel.onsen ? "✓" : "–"} 온천·대욕장</li>
                  </ul>
                </article>
                <article>
                  <h3>교통·서비스</h3>
                  <ul>
                    <li>{hotel.parking ? "✓" : "–"} 주차장</li>
                    <li>{hotel.airport_shuttle ? "✓" : "–"} 공항 셔틀</li>
                    <li>{hotel.luggage_storage ? "✓" : "–"} 짐 보관</li>
                    <li>{hotel.front_desk_24h ? "✓" : "–"} 24시간 프런트</li>
                    <li>✓ 역에서 {hotel.station_distance}m</li>
                    <li>{hotel.accessible ? "✓" : "–"} 장애인 편의시설</li>
                  </ul>
                </article>
                <article>
                  <h3>예약·투숙 정책</h3>
                  <ul>
                    <li>
                      {hotel.free_cancellation ? "✓" : "–"} 무료 취소 상품
                    </li>
                    <li>{hotel.pay_at_hotel ? "✓" : "–"} 현장 결제 상품</li>
                    <li>{hotel.breakfast ? "✓" : "–"} 조식 상품</li>
                    <li>{hotel.family_room ? "✓" : "–"} 가족 객실</li>
                    <li>{hotel.pet_friendly ? "✓" : "–"} 반려동물 동반</li>
                    <li>{hotel.balcony ? "✓" : "–"} 발코니 객실</li>
                  </ul>
                </article>
              </div>
            </section>
            {reviewItems.length > 0 && (
              <section className="reviewsSection">
                <div className="reviewSummary">
                  <div className="reviewScore">{hotel.rating.toFixed(1)}</div>
                  <div>
                    <span>GUEST REVIEWS</span>
                    <h2>투숙객 리뷰 {hotel.reviews.toLocaleString()}개</h2>
                    <p>청결도, 위치, 서비스 등 항목별 평가를 확인하세요.</p>
                  </div>
                </div>
                <div className="scoreBreakdown">
                  {[
                    ["청결도", 0.2],
                    ["위치", 0.4],
                    ["서비스", 0.1],
                    ["가격 대비 만족도", -0.2],
                    ["시설", -0.1],
                  ].map(([label, delta]) => {
                    const score = Math.max(
                      5,
                      Math.min(10, hotel.rating + Number(delta)),
                    );
                    return (
                      <div key={String(label)}>
                        <span>{label}</span>
                        <div>
                          <i style={{ width: `${score * 10}%` }} />
                        </div>
                        <b>{score.toFixed(1)}</b>
                      </div>
                    );
                  })}
                </div>
                <div className="reviewList">
                  {reviewItems.map((review) => (
                    <article key={review.review_id}>
                      <div className="reviewAuthor">
                        <div>{review.name.slice(0, 1)}</div>
                        <p>
                          <strong>{review.name}</strong>
                          <small>{review.country}</small>
                        </p>
                        <b>{review.score.toFixed(1)}</b>
                      </div>
                      <h3>{review.title}</h3>
                      <p>{review.body}</p>
                      <small>{review.stay}</small>
                    </article>
                  ))}
                </div>
                <p className="reviewNote">
                  리뷰 내용과 항목별 점수는 사용자 행동 연구를 위한 시뮬레이션
                  데이터입니다.
                </p>
              </section>
            )}
            <section className="roomSection">
              <div className="stayCalendar">
                <div className="calendarHeader">
                  <div>
                    <span>CHANGE STAY DATES</span>
                    <h2>달력에서 날짜를 다시 선택하세요</h2>
                    <p>
                      {c.checkin} → {c.checkout} · {nights()}박
                    </p>
                  </div>
                  <div>
                    <button
                      disabled={calendarMonth === "2026-01"}
                      onClick={() => {
                        const d = new Date(`${calendarMonth}-01T00:00:00Z`);
                        d.setUTCMonth(d.getUTCMonth() - 1);
                        setCalendarMonth(d.toISOString().slice(0, 7));
                      }}
                    >
                      ←
                    </button>
                    <strong>
                      {monthYear}년 {monthIndex + 1}월
                    </strong>
                    <button
                      disabled={calendarMonth === "2026-12"}
                      onClick={() => {
                        const d = new Date(`${calendarMonth}-01T00:00:00Z`);
                        d.setUTCMonth(d.getUTCMonth() + 1);
                        setCalendarMonth(d.toISOString().slice(0, 7));
                      }}
                    >
                      →
                    </button>
                  </div>
                </div>
                <div className="calendarWeek">
                  {["일", "월", "화", "수", "목", "금", "토"].map((day) => (
                    <b key={day}>{day}</b>
                  ))}
                </div>
                <div className="calendarGrid">
                  {calendarCells.map((date, index) =>
                    date ? (
                      <button
                        key={date}
                        className={[
                          date === c.checkin ? "checkin" : "",
                          date === c.checkout ? "checkout" : "",
                          date > c.checkin && date < c.checkout
                            ? "inRange"
                            : "",
                        ].join(" ")}
                        disabled={!pickingCheckout && date === "2026-12-31"}
                        onClick={() => selectCalendarDate(date)}
                        aria-label={date}
                      >
                        {Number(date.slice(-2))}
                      </button>
                    ) : (
                      <span key={`blank-${index}`} />
                    ),
                  )}
                </div>
                <p className="calendarHelp">
                  {busy
                    ? "선택한 날짜의 객실 재고를 확인하고 있습니다…"
                    : pickingCheckout
                      ? "체크아웃 날짜를 선택하세요."
                      : "체크인 날짜를 선택하세요."}
                </p>
              </div>
              <div className="roomTitle">
                <div>
                  <span>AVAILABLE ROOMS</span>
                  <h2>객실과 요금제를 직접 선택하세요</h2>
                </div>
                {[
                  ["freeCancellation", "무료 취소"],
                  ["payAtHotel", "현장 결제"],
                  ["breakfast", "조식"],
                  ["familyRoom", "가족 객실"],
                  ["petFriendly", "반려동물"],
                  ["pool", "수영장"],
                  ["spa", "스파"],
                  ["balcony", "발코니"],
                  ["bathtub", "욕조"],
                  ["nonSmoking", "금연"],
                  ["cityView", "시티뷰"],
                  ["twinBed", "트윈베드"],
                  ["airConditioning", "에어컨"],
                  ["kitchen", "주방"],
                  ["washingMachine", "세탁기"],
                  ["soundproof", "방음"],
                ].filter(([key]) => c[key]).length > 0 && (
                  <p className="requested">
                    검색 조건:{" "}
                    {[
                      ["freeCancellation", "무료 취소"],
                      ["payAtHotel", "현장 결제"],
                      ["breakfast", "조식"],
                      ["familyRoom", "가족 객실"],
                      ["petFriendly", "반려동물"],
                      ["pool", "수영장"],
                      ["spa", "스파"],
                      ["balcony", "발코니"],
                      ["bathtub", "욕조"],
                      ["nonSmoking", "금연"],
                      ["cityView", "시티뷰"],
                      ["twinBed", "트윈베드"],
                      ["airConditioning", "에어컨"],
                      ["kitchen", "주방"],
                      ["washingMachine", "세탁기"],
                      ["soundproof", "방음"],
                    ]
                      .filter(([key]) => c[key])
                      .map(([, label]) => label)
                      .join(" · ")}
                  </p>
                )}
              </div>
              <div className="roomList">
                {rooms.map((r) => (
                  <article
                    key={r.id}
                    className={`room ${room?.id === r.id ? "selected" : ""} ${
                      !r.available ? "unavailable" : ""
                    }`}
                  >
                    <div>
                      <h3>{r.name}</h3>
                      <p>
                        {r.bed_type} · {r.view_type} · {r.size_sqm}㎡ · 최대{" "}
                        {r.capacity}명
                      </p>
                      <div className="badges">
                        <b>{r.breakfast ? "조식 포함" : "조식 불포함"}</b>
                        <b>{r.free_cancellation ? "무료 취소" : "환불 불가"}</b>
                        <b>{r.pay_at_hotel ? "현장 결제" : "선결제"}</b>
                        <b>
                          {r.spa_access ? "스파 이용 가능" : "스파 이용 불가"}
                        </b>
                        <b>
                          {r.pool_access
                            ? "수영장 이용 가능"
                            : "수영장 이용 불가"}
                        </b>
                        <b>{r.balcony ? "발코니" : "발코니 없음"}</b>
                        <b>
                          {r.pet_friendly ? "반려동물 가능" : "반려동물 불가"}
                        </b>
                        <b>{r.family_room ? "가족 객실" : "일반 객실"}</b>
                        <b>{r.bathtub ? "욕조" : "샤워"}</b>
                        <b>{r.smoking ? "흡연 가능" : "금연"}</b>
                        <b>{r.air_conditioning ? "에어컨" : "에어컨 없음"}</b>
                        <b>{r.kitchen ? "객실 내 주방" : "주방 없음"}</b>
                        <b>{r.washing_machine ? "세탁기" : "세탁기 없음"}</b>
                        <b>{r.soundproof ? "방음 객실" : "일반 방음"}</b>
                      </div>
                    </div>
                    <div className="roomPrice">
                      {r.available ? (
                        <small>이 가격으로 {r.units_left}개 남음</small>
                      ) : (
                        <strong className="soldOut">예약 마감</strong>
                      )}
                      <strong>
                        {(hotel.price + r.price_modifier).toLocaleString()}원
                      </strong>
                      {!r.available && <small>{r.availability_reason}</small>}
                      <button
                        className={room?.id === r.id ? "solid" : ""}
                        disabled={!r.available}
                        onClick={() => choose(r)}
                      >
                        {!r.available
                          ? "선택한 날짜에 예약 불가"
                          : room?.id === r.id
                            ? "선택됨"
                            : "객실 선택"}
                      </button>
                      <button disabled={!r.available} onClick={() => void toggleCart(hotel, r)}>
                        {cart.some((item) => item.id === `${hotel.id}:${r.id}:${c.checkin}:${c.checkout}`)
                          ? "장바구니에서 빼기" : "장바구니 담기"}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
              <button
                className="bookBar solid"
                disabled={!room}
                onClick={start}
              >
                {room ? `${room.name} 예약하기 →` : "먼저 객실을 선택하세요"}
              </button>
            </section>
          </>
        )}
        {screen === "booking" && hotel && room && (
          <section className="checkout">
            <span>BOOKING REVIEW</span>
            <h1>예약 정보를 확인하세요</h1>
            <div className="box">
              <h2>{hotel.name}</h2>
              <h3>{room.name}</h3>
              <p>
                {room.bed_type} · {room.view_type} · {room.size_sqm}㎡
              </p>
              <p>
                {c.checkin} — {c.checkout} · {c.guests}명 · 객실 {c.rooms}개
              </p>
              <p>
                {room.free_cancellation ? "무료 취소" : "환불 불가"} ·{" "}
                {room.pay_at_hotel ? "현장 결제" : "선결제"} ·{" "}
                {room.spa_access ? "스파 가능" : "스파 불가"}
              </p>
              <h2>
                총{" "}
                {(
                  (hotel.price + room.price_modifier) *
                  nights() *
                  c.rooms
                ).toLocaleString()}
                원
              </h2>
              <div className="actions">
                <button className="solid" onClick={done}>
                  예약 확정
                </button>
                <button onClick={cancel}>취소하고 객실 선택으로</button>
              </div>
            </div>
          </section>
        )}
        {screen === "complete" && (
          <section className="complete">
            <div>✓</div>
            <span>PARTICIPATION COMPLETE</span>
            <h1>조사에 참여해 주셔서 감사합니다</h1>
            <p>
              끝까지 진행해 주신 예약 과정은 프로젝트 연구에 매우 큰 도움이 됩니다.
            </p>
            <p className="simulationNotice">
              이 사이트는 연구를 위한 예약 시뮬레이션입니다. 실제 숙소 예약이나 결제는 이루어지지 않습니다.
            </p>
            <p>실험 기록 번호 <code>{reservation}</code></p>
            <button className="solid" onClick={() => setScreen("search")}>
              새로운 여행 찾기
            </button>
          </section>
        )}
        {screen === "admin" && admin && (
          <>
            <section className="top">
              <div>
                <span>BEHAVIOR DATA CONSOLE</span>
                <h1>실험 현황</h1>
              </div>
              <button onClick={() => setScreen("search")}>사용자 화면</button>
            </section>
            <div className="stats">
              {Object.entries(admin.counts || {}).map(([k, v]) => (
                <div key={k}>
                  <span>{k}</span>
                  <strong>{String(v)}</strong>
                </div>
              ))}
            </div>
            <section className="experiment">
              <h2>검색–객실 옵션 불일치 실험</h2>
              <div>
                {Object.entries(admin.experiment || {}).map(([k, v]: any) => (
                  <article key={k}>
                    <span>
                      {k === "control"
                        ? "대조군 · 옵션 일치"
                        : "실험군 · 옵션 불일치"}
                    </span>
                    <strong>예약 전환 {v.conversion}%</strong>
                    <p>
                      객실 선택률 {v.selectionRate}% · 평균 검색 {v.avgSearches}
                      회
                    </p>
                    <p>
                      {v.sessions}개 세션 · 선택 {v.selections}건 · 예약{" "}
                      {v.bookings}건
                    </p>
                  </article>
                ))}
              </div>
              <p>
                평균 검색 횟수로 검색 효율을, 객실 선택률과 예약 전환율로 예약
                성과를 비교합니다.
              </p>
            </section>
            <section className="dataConsole">
              <div className="consoleHeading">
                <div>
                  <span>8-TABLE DATASET · USER JOURNEY</span>
                  <h2>분석 데이터 콘솔</h2>
                  <p>테이블을 선택해 전체 칼럼을 확인하고 CSV로 내려받을 수 있습니다.</p>
                </div>
                <div className="consoleActions">
                  <button
                    className="solid"
                    disabled={!admin?.datasets || busy}
                    onClick={downloadAllCsv}
                  >
                    전체 CSV 한 번에 다운로드
                  </button>
                  <a className="reportDownload" href="/staytrace-site-production-kit.zip" download>
                    전체 제작 자료
                  </a>
                  <a className="reportDownload" href="/staytrace-project-report.md" download>
                    사이트 기획 보고서
                  </a>
                  {adminTable !== "TRASH" && adminTable !== "JOURNEY" && (
                    <button
                      className="solid"
                      disabled={!admin.datasets?.[adminTable]?.length}
                      onClick={() => downloadCsv(adminTable, admin.datasets[adminTable])}
                    >
                      {adminTable}.csv 다운로드
                    </button>
                  )}
                </div>
              </div>
              <div className="dataTabs">
                {["HOTEL", "ROOM", "SEARCH", "SEARCH_FILTER", "USER", "EVENT", "SEARCH_RESULT", "BOOKING"].map((table) => (
                  <button
                    key={table}
                    className={adminTable === table ? "active" : ""}
                    onClick={() => { setAdminTable(table); setSelectedAdmin(new Set()); setAdminColumnFilters({}); }}
                  >
                    {table} <small>{admin.datasets?.[table]?.length || 0}</small>
                  </button>
                ))}
                <button
                  className={adminTable === "JOURNEY" ? "active" : ""}
                  onClick={() => { setAdminTable("JOURNEY"); setSelectedAdmin(new Set()); setAdminColumnFilters({}); }}
                >
                  USER JOURNEY <small>{journeySessions.length}</small>
                </button>
                <button
                  className={adminTable === "TRASH" ? "active trashTab" : "trashTab"}
                  onClick={() => { setAdminTable("TRASH"); setSelectedAdmin(new Set()); setAdminColumnFilters({}); }}
                >
                  휴지통 <small>{admin.deleted?.length || 0}</small>
                </button>
              </div>
              {adminTable === "JOURNEY" && (
                <div className="adminFilterBar journeyFilters">
                  <select value={adminUser} onChange={(event) => setAdminUser(event.target.value)} aria-label="여정 사용자 선택">
                    <option value="">전체 사용자 여정</option>
                    {(admin?.userOptions || []).map((user: any) => (
                      <option key={user.user_id} value={user.user_id}>{user.user_name} · {user.user_id}</option>
                    ))}
                  </select>
                  <input value={adminQuery} onChange={(event) => setAdminQuery(event.target.value)}
                    placeholder="이벤트·세션·호텔 검색" aria-label="사용자 여정 검색" />
                  <button onClick={() => { setAdminUser(""); setAdminQuery(""); }}>여정 필터 초기화</button>
                  <small>세션 {journeySessions.length}개 · 이벤트 {journeyEvents.length}개</small>
                </div>
              )}
              {adminTable !== "JOURNEY" && (
              <div className="adminFilterBar">
                <input
                  value={adminQuery}
                  onChange={(event) => { setAdminQuery(event.target.value); setSelectedAdmin(new Set()); }}
                  placeholder="현재 자료에서 검색"
                  aria-label="관리 데이터 검색"
                />
                <select value={adminUser} onChange={(event) => { setAdminUser(event.target.value); setSelectedAdmin(new Set()); }} aria-label="사용자별 필터">
                  <option value="">전체 사용자</option>
                  {(admin?.userOptions || []).map((user: any) => (
                    <option key={user.user_id} value={user.user_id}>{user.user_name} · {user.user_id}</option>
                  ))}
                </select>
                {adminTable === "TRASH" && (
                  <select value={trashTable} onChange={(event) => { setTrashTable(event.target.value); setSelectedAdmin(new Set()); }} aria-label="휴지통 테이블 필터">
                    <option value="">전체 테이블</option>
                    {["HOTEL", "ROOM", "SEARCH", "SEARCH_FILTER", "USER", "EVENT", "SEARCH_RESULT", "BOOKING"].map((table) =>
                      <option key={table} value={table}>{table}</option>)}
                  </select>
                )}
                <button onClick={toggleAllVisible} disabled={!visibleSelectionKeys.length}>
                  {allVisibleSelected ? "필터 결과 전체 선택 해제" : `필터 결과 전체 선택 (${visibleSelectionKeys.length})`}
                </button>
                <button onClick={() => { setAdminQuery(""); setAdminUser(""); setTrashTable(""); setAdminColumnFilters({}); setSelectedAdmin(new Set()); }}>
                  모든 필터 초기화
                </button>
                {adminTable === "TRASH" ? (
                  <button className="solid" disabled={!selectedAdmin.size || busy}
                    onClick={() => bulkRestoreAdmin([...selectedAdmin].map((key) => {
                      const split = key.indexOf(":");
                      return { table: key.slice(0, split), rowId: key.slice(split + 1) };
                    }))}>
                    선택 {selectedAdmin.size}개 복구
                  </button>
                ) : (
                  <>
                    <button className="dangerBtn" disabled={!selectedAdmin.size || busy}
                      onClick={() => bulkDeleteAdmin([...selectedAdmin].map((key) => ({
                        table: adminTable, rowId: key.slice(key.indexOf(":") + 1),
                      })))}>
                      선택 {selectedAdmin.size}개 삭제
                    </button>
                    <button className="dangerBtn filteredDelete" disabled={!filteredAdminRows.length || busy}
                      onClick={() => bulkDeleteAdmin(filteredAdminRows.map((row: any) => ({
                        table: adminTable, rowId: adminRowId(adminTable, row),
                      })))}>
                      필터 결과 {filteredAdminRows.length}개 모두 삭제
                    </button>
                  </>
                )}
                <small>전체 {adminTable === "TRASH" ? filteredDeletedRows.length : filteredAdminRows.length}개 · 표 화면 최대 250개</small>
              </div>
              )}
              {adminTable === "JOURNEY" ? (
                <div className="journeyBoard">
                  {journeySessions.map((session: any) => (
                    <article className="journeySession" key={session.sessionId}>
                      <header>
                        <div><span>SESSION</span><h3>{session.sessionId}</h3></div>
                        <p>사용자 {session.userId} · 이벤트 {session.events.length}개</p>
                      </header>
                      <ol className="journeyTimeline">
                        {session.events.map((event: any) => (
                          <li key={event.event_id}>
                            <time>{event.event_at}</time>
                            <div>
                              <b>{event.event_type}</b>
                              <small>{[
                                event.search_id && `검색 ${event.search_id}`,
                                event.hotel_id && `호텔 ${event.hotel_id}`,
                              ].filter(Boolean).join(" · ") || "공통 행동"}</small>
                            </div>
                            {event.event_properties_json && (
                              <details><summary>세부 데이터</summary><code>{event.event_properties_json}</code></details>
                            )}
                          </li>
                        ))}
                      </ol>
                    </article>
                  ))}
                  {!journeySessions.length && <p className="emptyDataset">선택한 조건에 맞는 사용자 여정이 없습니다.</p>}
                </div>
              ) : adminTable === "TRASH" ? (
                <div className="table dataTable">
                  <table>
                    <thead>
                      <tr><th>선택</th><th>테이블</th><th>사용자</th><th>행 ID</th><th>삭제 시간</th><th>데이터</th><th>관리</th></tr>
                      <tr className="columnFilterRow">
                        <th></th>
                        {["table_name", "owner_user_id", "row_id", "deleted_at", "snapshot"].map((column) => (
                          <th key={column}><input value={adminColumnFilters[column] || ""}
                            onChange={(event) => setColumnFilter(column, event.target.value)}
                            placeholder={`${column} 필터`} aria-label={`${column} 칼럼 필터`} /></th>
                        ))}
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredDeletedRows.map((row: any) => (
                        <tr key={`${row.table_name}:${row.row_id}`}>
                          <td><input type="checkbox" aria-label={`${row.row_id} 선택`}
                            checked={selectedAdmin.has(adminSelectionKey(row.table_name, row.row_id))}
                            onChange={() => toggleAdminSelection(row.table_name, row.row_id)} /></td>
                          <td><b>{row.table_name}</b></td><td>{row.owner_user_id || "-"}</td><td>{row.row_id}</td><td>{row.deleted_at}</td>
                          <td className="snapshotCell">{row.snapshot}</td>
                          <td><button onClick={() => restoreAdminRow(row.table_name, row.row_id)}>복구</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!filteredDeletedRows.length && <p className="emptyDataset">조건에 맞는 휴지통 자료가 없습니다.</p>}
                </div>
              ) : (
                <div className="table dataTable">
                  {!!datasetColumns.length && (
                    <table>
                      <thead>
                        <tr>
                          <th>선택</th>
                          {datasetColumns.map(([column, label]) => <th key={column}>{label}<small>{column}</small></th>)}
                          <th>관리</th>
                        </tr>
                        <tr className="columnFilterRow">
                          <th></th>
                          {datasetColumns.map(([column]) => (
                            <th key={column}><input value={adminColumnFilters[column] || ""}
                              onChange={(event) => setColumnFilter(column, event.target.value)}
                              placeholder={`${column} 필터`} aria-label={`${column} 칼럼 필터`} /></th>
                          ))}
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredAdminRows.slice(0, 250).map((row: any, index: number) => (
                          <tr key={index}>
                            <td><input type="checkbox" aria-label={`${adminRowId(adminTable, row)} 선택`}
                              checked={selectedAdmin.has(adminSelectionKey(adminTable, adminRowId(adminTable, row)))}
                              onChange={() => toggleAdminSelection(adminTable, adminRowId(adminTable, row))} /></td>
                            {datasetColumns.map(([column]) => <td key={column}>{String(row[column] ?? "")}</td>)}
                            <td><button className="dangerBtn" onClick={() => deleteAdminRow(adminTable, row)}>삭제</button></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  {!filteredAdminRows.length && <p className="emptyDataset">조건에 맞는 데이터가 없습니다.</p>}
                </div>
              )}
            </section>
          </>
        )}
      </main>
    </>
  );
}
