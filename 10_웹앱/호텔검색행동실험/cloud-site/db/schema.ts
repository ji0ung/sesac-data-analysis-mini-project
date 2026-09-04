import { sqliteTable, text, integer, real } from "drizzle-orm/sqlite-core";

export const users = sqliteTable("users", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  createdAt: text("created_at").notNull(),
});
export const sessions = sqliteTable("sessions", {
  id: text("id").primaryKey(),
  userId: text("user_id").notNull(),
  startedAt: text("started_at").notNull(),
  endedAt: text("ended_at"),
});
export const hotels = sqliteTable("hotels", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  city: text("city").notNull(),
  type: text("type").notNull(),
  grade: integer("grade").notNull(),
  rating: real("rating").notNull(),
  price: integer("price").notNull(),
  reviews: integer("reviews").notNull(),
  stationDistance: integer("station_distance").notNull(),
  amenities: text("amenities").notNull(),
  freeCancellation: integer("free_cancellation").notNull(),
  payAtHotel: integer("pay_at_hotel").notNull(),
  breakfast: integer("breakfast").notNull(),
  familyRoom: integer("family_room").notNull(),
  petFriendly: integer("pet_friendly").notNull(),
  pool: integer("pool").notNull(),
  spa: integer("spa").notNull(),
  balcony: integer("balcony").notNull().default(0),
  chain: text("chain"),
});
export const searches = sqliteTable("searches", {
  id: text("id").primaryKey(),
  userId: text("user_id").notNull(),
  sessionId: text("session_id").notNull(),
  parentId: text("parent_id"),
  createdAt: text("created_at").notNull(),
  conditions: text("conditions").notNull(),
  resultCount: integer("result_count").notNull(),
});
export const events = sqliteTable("events", {
  id: text("id").primaryKey(),
  userId: text("user_id").notNull(),
  sessionId: text("session_id").notNull(),
  searchId: text("search_id"),
  hotelId: text("hotel_id"),
  name: text("name").notNull(),
  page: text("page").notNull(),
  properties: text("properties").notNull(),
  createdAt: text("created_at").notNull(),
});
export const reservations = sqliteTable("reservations", {
  id: text("id").primaryKey(),
  userId: text("user_id").notNull(),
  sessionId: text("session_id").notNull(),
  searchId: text("search_id").notNull(),
  hotelId: text("hotel_id").notNull(),
  totalPrice: integer("total_price").notNull(),
  status: text("status").notNull(),
  createdAt: text("created_at").notNull(),
});
export const roomInventory = sqliteTable("room_inventory", {
  id: text("id").primaryKey(),
  hotelId: text("hotel_id").notNull(),
  name: text("name").notNull(),
  bedType: text("bed_type").notNull(),
  viewType: text("view_type").notNull(),
  sizeSqm: integer("size_sqm").notNull(),
  capacity: integer("capacity").notNull(),
  breakfast: integer("breakfast").notNull(),
  freeCancellation: integer("free_cancellation").notNull(),
  payAtHotel: integer("pay_at_hotel").notNull(),
  spaAccess: integer("spa_access").notNull(),
  poolAccess: integer("pool_access").notNull().default(0),
  petFriendly: integer("pet_friendly").notNull().default(0),
  balcony: integer("balcony").notNull().default(0),
  bathtub: integer("bathtub").notNull(),
  smoking: integer("smoking").notNull(),
  unitsLeft: integer("units_left").notNull(),
  priceModifier: integer("price_modifier").notNull(),
});
