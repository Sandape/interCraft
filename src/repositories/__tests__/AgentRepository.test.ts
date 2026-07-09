import { describe, expect, it } from 'vitest'
import { resolveQrcodeSrc } from '../AgentRepository'
import type { QrcodeData } from '../AgentRepository'

describe('AgentRepository QR code helpers', () => {
  it('uses the renderable QR image URL as the img src without base64', () => {
    const data: QrcodeData = {
      qrcode_token: 'a46fb64431ed99597887d23b442c987c',
      qrcode_url:
        'https://liteapp.weixin.qq.com/q/7GiQu1?qrcode=a46fb64431ed99597887d23b442c987c&bot_type=3',
      qrcode_image_url:
        '/api/v1/agent/wechat/qrcode/image?qrcode_token=a46fb64431ed99597887d23b442c987c',
      expires_at: '2026-07-08T12:05:00Z',
      expires_in_sec: 300,
    }

    expect(resolveQrcodeSrc(data)).toBe(data.qrcode_image_url)
    expect(resolveQrcodeSrc(data)).not.toMatch(/^data:image\/png;base64,/)
  })
})
