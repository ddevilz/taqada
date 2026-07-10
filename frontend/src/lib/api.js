import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const client = axios.create({ baseURL: API, timeout: 30000 });

export const api = {
  root: () => client.get("/").then((r) => r.data),
  config: () => client.get("/config").then((r) => r.data),
  seed: () => client.post("/seed").then((r) => r.data),
  invoices: (status) =>
    client.get("/invoices", { params: status ? { status } : {} }).then((r) => r.data),
  invoice: (id) => client.get(`/invoices/${id}`).then((r) => r.data),
  summary: () => client.get("/dashboard/summary").then((r) => r.data),
  activity: (limit = 40) =>
    client.get("/dashboard/activity", { params: { limit } }).then((r) => r.data),
  escalations: () => client.get("/dashboard/escalations").then((r) => r.data),
  runAgent: () => client.post("/agent/run").then((r) => r.data),
  chaseOne: (invoice_id) => client.post("/agent/chase", { invoice_id }).then((r) => r.data),
  simulateReply: (invoice_id, text) =>
    client.post("/agent/simulate-reply", { invoice_id, text }).then((r) => r.data),
  markPaid: (invoice_id) =>
    client.post("/demo/mark-paid", { invoice_id }).then((r) => r.data),
  previewMessage: (invoice_id, rung) =>
    client.post("/messages/preview", { invoice_id, rung }).then((r) => r.data),
  telegramLink: (debtor_id) =>
    client.get(`/debtors/${debtor_id}/telegram-link`).then((r) => r.data),
};
