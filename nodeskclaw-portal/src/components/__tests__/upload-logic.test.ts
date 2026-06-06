import { describe, expect, it } from 'vitest'

describe('upload scan status logic', () => {
  function isScanBlocked(scanStatus?: string): boolean {
    return scanStatus === 'pending' || scanStatus === 'blocked' || scanStatus === 'failed'
  }

  describe('isScanBlocked', () => {
    it('returns true for pending scan', () => {
      expect(isScanBlocked('pending')).toBe(true)
    })

    it('returns true for blocked scan', () => {
      expect(isScanBlocked('blocked')).toBe(true)
    })

    it('returns true for failed scan', () => {
      expect(isScanBlocked('failed')).toBe(true)
    })

    it('returns false for clean', () => {
      expect(isScanBlocked('clean')).toBe(false)
    })

    it('returns false for skipped', () => {
      expect(isScanBlocked('skipped')).toBe(false)
    })

    it('returns false for undefined', () => {
      expect(isScanBlocked(undefined)).toBe(false)
    })
  })

  describe('file downloadable logic', () => {
    type TestFileRef = {
      download_url_available?: boolean
      status?: string
      scan_status?: string
    }

    function isDownloadable(ref: TestFileRef): boolean {
      return ref.download_url_available !== false
        && ref.status !== 'unavailable'
        && !isScanBlocked(ref.scan_status)
    }

    it('allows download for clean file with available URL', () => {
      expect(isDownloadable({
        download_url_available: true,
        status: 'available',
        scan_status: 'clean',
      })).toBe(true)
    })

    it('blocks download when scan pending', () => {
      expect(isDownloadable({
        download_url_available: true,
        status: 'available',
        scan_status: 'pending',
      })).toBe(false)
    })

    it('blocks download when file blocked', () => {
      expect(isDownloadable({
        download_url_available: true,
        status: 'available',
        scan_status: 'blocked',
      })).toBe(false)
    })

    it('blocks download when status unavailable', () => {
      expect(isDownloadable({
        download_url_available: true,
        status: 'unavailable',
        scan_status: 'clean',
      })).toBe(false)
    })

    it('blocks download when url not available', () => {
      expect(isDownloadable({
        download_url_available: false,
        status: 'available',
        scan_status: 'clean',
      })).toBe(false)
    })

    it('allows download for skipped scan', () => {
      expect(isDownloadable({
        download_url_available: true,
        status: 'available',
        scan_status: 'skipped',
      })).toBe(true)
    })
  })

  describe('gateway warning logic', () => {
    function shouldShowGatewayWarning(
      sharedFileMaxMb: number,
      largeFileMaxMb: number,
      gatewayMb: number,
    ): boolean {
      const appMax = Math.max(sharedFileMaxMb, largeFileMaxMb)
      return appMax > gatewayMb
    }

    it('shows warning when shared file limit exceeds gateway', () => {
      expect(shouldShowGatewayWarning(200, 100, 50)).toBe(true)
    })

    it('shows warning when large file limit exceeds gateway', () => {
      expect(shouldShowGatewayWarning(40, 2048, 50)).toBe(true)
    })

    it('does not show warning when both under gateway', () => {
      expect(shouldShowGatewayWarning(20, 40, 50)).toBe(false)
    })

    it('does not show warning when equal to gateway', () => {
      expect(shouldShowGatewayWarning(50, 30, 50)).toBe(false)
    })
  })
})
