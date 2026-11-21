// Local desktop adapter for the fixed cnc_admin sudo switch.
import { execFile } from 'node:child_process'
import { maintenanceRequiredMessage } from '../bridge.js'

const helper = '/usr/lib/betterlinuxcnc/account-management/cnc-maint/cnc-maint-account'

type Operation = 'status' | 'enable' | 'disable' | 'admin-sudo-status' | 'admin-sudo-enable' | 'admin-sudo-disable' | 'admin-setup-required' | 'admin-sudo-enroll'

function request(operation: Operation, input = ''): Promise<boolean> {
  return new Promise((resolve, reject) => {
    const child = execFile(helper, ['request', operation], {
      timeout: 20000, maxBuffer: 1024, encoding: 'utf8',
    }, (error, stdout) => {
      if (error && ['status', 'enable', 'disable'].includes(operation)) {
        return reject(new Error(operation === 'disable' ? '关闭失败，请核对运维密码和本机桌面状态' : '无法确认运维账户状态，请检查机床桌面和账户服务'))
      }
      if (error) return reject(new Error(operation === 'admin-sudo-enroll'
        ? '设置失败，请核对 cnc-maint 运维密码和新的管理员密码'
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

export function maintenanceStatus() {
  return request('status')
}

export async function requireMaintenance() {
  if (!await maintenanceStatus()) throw new Error(maintenanceRequiredMessage)
}

export async function setMaintenanceEnabled(enabled: unknown, password: unknown) {
  if (typeof enabled !== 'boolean' || typeof password !== 'string' || !password.length
    || Buffer.byteLength(password) > 512 || /\p{Cc}/u.test(password)) throw new Error('请输入有效的运维密码')
  if (enabled && (Buffer.byteLength(password) < 8 || Buffer.byteLength(password) > 256 || password.includes(':'))) {
    throw new Error('密码需为 8 至 256 字节，不能包含冒号或控制字符')
  }
  const state = await request(enabled ? 'enable' : 'disable', password)
  if (state !== enabled) throw new Error('运维账户状态未确认')
  return state
}

export function adminSudoStatus() {
  return request('admin-sudo-status')
}

export async function adminSetupRequired() {
  await requireMaintenance()
  return request('admin-setup-required')
}

export async function enrollAdmin(maintenancePassword: unknown, password: unknown) {
  if (typeof maintenancePassword !== 'string' || !maintenancePassword.length
    || Buffer.byteLength(maintenancePassword) > 512 || /\p{Cc}/u.test(maintenancePassword)) throw new Error('请输入有效的 cnc-maint 运维密码')
  if (typeof password !== 'string' || Buffer.byteLength(password) < 8
    || Buffer.byteLength(password) > 256 || /[:\p{Cc}]/u.test(password)) throw new Error('密码需为 8 至 256 字节，不能包含冒号或控制字符')
  await requireMaintenance()
  const applied = await request('admin-sudo-enroll', `${maintenancePassword}\n${password}`)
  if (!applied) throw new Error('管理员服务未确认开通')
  return applied
}

export async function setAdminSudo(enabled: unknown, password: unknown) {
  if (typeof enabled !== 'boolean' || typeof password !== 'string' || password.length === 0
    || Buffer.byteLength(password) > 512 || /\p{Cc}/u.test(password)) throw new Error('请输入有效的管理员密码')
  await requireMaintenance()
  const applied = await request(enabled ? 'admin-sudo-enable' : 'admin-sudo-disable', password)
  if (applied !== enabled) throw new Error('管理员服务未确认所请求的 sudo 状态')
  return applied
}
