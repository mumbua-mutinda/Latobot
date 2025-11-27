import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_BASE || 'http://127.0.0.1:8000';

export async function chat(session_id, message) {
  const res = await axios.post(`${API_BASE}/chat`, { session_id, message });
  return res.data;
}

export async function getProducts() {
  const res = await axios.get(`${API_BASE}/products`);
  return res.data;
}

export async function getProduct(skuOrName) {
  const res = await axios.get(`${API_BASE}/product/${encodeURIComponent(skuOrName)}`);
  return res.data;
}
