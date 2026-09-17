import { describe, expect, it } from 'vitest';
import { PDFDocument } from 'pdf-lib';
import { readFile } from 'node:fs/promises';
import { createSignedArtifacts } from '../src/pdf';

describe('signed PDF generation', () => {
  it('stamps every original page and appends a certificate', async () => {
    const original = await PDFDocument.create();
    original.addPage(); original.addPage();
    const bytes = await original.save();
    const font = await readFile(new URL('./fixtures/NotoSansJP-Test.otf', import.meta.url));
    const result = await createSignedArtifacts(bytes.buffer as ArrayBuffer, font.buffer.slice(font.byteOffset, font.byteOffset + font.byteLength) as ArrayBuffer, {
      contractId: 'contract-1', title: 'Cloudflare PoC 実利用検証契約', issuer: '株式会社テスト', signer: '山田太郎', signerEmail: 'signer@example.com',
      originalSha256: 'a'.repeat(64), signedAt: '2026-01-01T00:00:00.000Z', ipAddress: '127.0.0.1', userAgent: 'vitest', auditHash: 'b'.repeat(64)
    });
    expect((await PDFDocument.load(result.certificate)).getPageCount()).toBe(1);
    expect((await PDFDocument.load(result.signed)).getPageCount()).toBe(3);
  });
});
