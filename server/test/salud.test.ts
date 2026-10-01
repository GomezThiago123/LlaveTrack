import request from 'supertest';
import { describe, expect, it } from 'vitest';
import { crearApp } from '../src/app.js';

describe('GET /api/salud', () => {
  it('responde ok', async () => {
    const res = await request(crearApp()).get('/api/salud');
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ ok: true });
  });
});
