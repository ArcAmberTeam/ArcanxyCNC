// Local desktop adapter for the fixed cnc_admin sudo switch.
import { execFile } from 'node:child_process'

const helper = '/usr/lib/betterlinuxcnc/account-management/cnc-maint/cnc-maint-account'

type Operation = 'admin-sudo-status' | 'admin-sudo-enable' | 'admin-sudo-disable' | 'admin-setup-required' | 'admin-sudo-enroll'

function request(operation: Operation, input = ''): Promise<boolean> {
  return new Promise((resolve, reject) => {
    const child = execFile(helper, ['request', operation], {
      timeout: 20000, maxBuffer: 1024, encoding: 'utf8',
    }, (error, stdout) => {
      if (error) return reject(new Error(operation === 'admin-sudo-enroll'
        ? '开通未确认，请核对开通码和新密码'
        : '无法确认管理员 sudo 状态，请检查账户认证和本机服务'))
      try {
        const reply = JSON.parse(stdout)
        const state = operation === 'admin-setup-required' ? reply?.setupRequired : reply?.enabled
        if (reply?.ok === true && typeof state === 'boolean') return resolve(state)
      } catch { /* Reject unconfirmed replies. */ }
      reject(new Error('管理员服务返回了无效状态'))
    })
    child.stdin?.on('error', () => reject(new Error('无法提交管理员请求')))
    child.stdin?.end(input)
  })
}

export function adminSudoStatus() {
  return request('admin-sudo-status')
}

export function adminSetupRequired() {
  return request('admin-setup-required')
}

export async function enrollAdmin(code: unknown, password: unknown) {
  if (typeof code !== 'string' || code.length > 39 || !/^[a-f\d-]+$/i.test(code)
    || code.replaceAll('-', '').length !== 32) throw new Error('开通码格式不正确')
  if (typeof password !== 'string' || Buffer.byteLength(password) < 8
    || Buffer.byteLength(password) > 256 || /[:\p{Cc}]/u.test(password)) throw new Error('密码需为 8 至 256 字节，不能包含冒号或控制字符')
  const applied = await request('admin-sudo-enroll', `${code}\n${password}`)
  if (!applied) throw new Error('管理员服务未确认开通')
  return applied
}

export async function setAdminSudo(enabled: unknown, password: unknown) {
  if (typeof enabled !== 'boolean' || typeof password !== 'string' || password.length === 0
    || Buffer.byteLength(password) > 512 || /\p{Cc}/u.test(password)) throw new Error('请输入有效的管理员密码')
  const applied = await request(enabled ? 'admin-sudo-enable' : 'admin-sudo-disable', password)
  if (applied !== enabled) throw new Error('管理员服务未确认所请求的 sudo 状态')
  return applied
}
