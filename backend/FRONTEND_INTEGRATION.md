# Panduan Integrasi Frontend React SAVESPEECH

Panduan ini menyediakan kode lengkap untuk menggantikan mock service di frontend React dengan koneksi API backend asli sesuai kontrak data.

---

## 1. Konfigurasi Environment (`frontend/.env`)
Pastikan variabel `VITE_API_URL` mengarah ke backend FastAPI:
```env
VITE_API_URL=http://localhost:8000
```

---

## 2. Berkas: `src/services/api.js`
Gantikan seluruh isi `src/services/api.js` dengan kode lengkap berikut:

```javascript
/**
 * Service API Dasar & Autentikasi SAVESPEECH
 */
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Penyimpanan token in-memory untuk keamanan
let inMemoryToken = null;
let logoutCallback = null;

export const setAuthToken = (token) => {
  inMemoryToken = token;
};

export const getAuthToken = () => inMemoryToken;

export const registerLogoutCallback = (cb) => {
  logoutCallback = cb;
};

export const request = async (endpoint, options = {}) => {
  const url = `${BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (inMemoryToken) {
    headers['Authorization'] = `Bearer ${inMemoryToken}`;
  }

  // Jika body berupa FormData (multipart upload), hapus Content-Type agar browser mengatur boundary otomatis
  if (options.body instanceof FormData) {
    delete headers['Content-Type'];
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  // Tangani 401 Unauthorized secara otomatis (Token kedaluwarsa atau rusak)
  if (response.status === 401) {
    inMemoryToken = null;
    if (logoutCallback) {
      logoutCallback();
    }
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const errorMessage = data?.error?.message || `Terjadi kesalahan (Kode: ${response.status})`;
    const error = new Error(errorMessage);
    error.code = data?.error?.code || response.status;
    error.status = response.status;
    throw error;
  }

  return data;
};

// API Autentikasi
export const authApi = {
  login: async (email, password) => {
    const data = await request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setAuthToken(data.token);
    return data;
  },

  register: async (nama, email, password) => {
    const data = await request('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ nama, email, password }),
    });
    setAuthToken(data.token);
    return data;
  },

  getMe: async () => {
    return await request('/api/auth/me', {
      method: 'GET',
    });
  },

  logout: () => {
    setAuthToken(null);
  },
};
```

---

## 3. Berkas: `src/services/analysisApi.js`
Gantikan seluruh isi `src/services/analysisApi.js` dengan kode lengkap berikut:

```javascript
import { request } from './api';

/**
 * Service Analisis Audio & Riwayat SAVESPEECH
 */
export const analysisApi = {
  // 1. Unggah berkas audio
  analyzeAudio: async (audioFile, saveHistory = false) => {
    const formData = new FormData();
    formData.append('file', audioFile);
    formData.append('saveHistory', saveHistory ? 'true' : 'false');

    return await request('/api/analyze', {
      method: 'POST',
      body: formData,
    });
  },

  // 2. Polling status pekerjaan
  getJobStatus: async (jobId) => {
    return await request(`/api/jobs/${jobId}`, {
      method: 'GET',
    });
  },

  // 3. Mengambil hasil analisis lengkap (in-memory)
  getResult: async (jobId) => {
    return await request(`/api/results/${jobId}`, {
      method: 'GET',
    });
  },

  // 4. Riwayat analisis tersimpan (opt-in)
  getHistory: async (page = 1, pageSize = 10) => {
    return await request(`/api/history?page=${page}&pageSize=${pageSize}`, {
      method: 'GET',
    });
  },

  // 5. Menghapus riwayat tersimpan
  deleteHistoryItem: async (id) => {
    return await request(`/api/results/${id}`, {
      method: 'DELETE',
    });
  },
};
```
