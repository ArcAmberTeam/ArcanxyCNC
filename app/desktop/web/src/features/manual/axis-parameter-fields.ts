// 定义轴参数表单的字段名称、单位和数值约束。
// Field labels, units, and numeric constraints for the axis parameter form.
export interface NumericField {
  key: string
  label: string
  unit?: string
  positive?: boolean
  index?: boolean
  integer?: boolean
}

export const measuredTravel = { key: 'measuredTravel', label: '实测行程', positive: true } as const
export const estimatedTravel = { key: 'estimatedTravel', label: '暂定行程', positive: true } as const

export const motionFields = [
  { key: 'min', label: '软限位下限' },
  { key: 'max', label: '软限位上限' },
  { key: 'maxFeed', label: '最大速度', positive: true },
] as const

export function axisFields(rotary: boolean): NumericField[] {
  const unit = rotary ? '°' : 'mm'
  const fields: NumericField[] = [
    { key: 'joint', label: '关节编号', index: true },
    { key: 'drive', label: '驱动通道', index: true },
    { key: 'scale', label: rotary ? '每度脉冲数' : '每毫米脉冲数', positive: true },
    { key: 'acceleration', label: '最大加速度', unit: unit + '/s²', positive: true },
    { key: 'homeSequence', label: '回零顺序', integer: true },
    { key: 'homeOffset', label: '回零偏移', unit },
  ]
  if (rotary) fields.push(
    { key: 'ratio', label: '传动比', unit: '电机转/转台转', positive: true },
    { key: 'mechanicalZero', label: '机械零位', unit },
    { key: 'angleMin', label: '机械转角下限', unit },
    { key: 'angleMax', label: '机械转角上限', unit },
  )
  return fields
}

export const rtcpModels = [
  { value: 'xyzac-trt-kins', label: 'AC 转台' },
  { value: 'xyzbc-trt-kins', label: 'BC 转台' },
] as const

export function geometryFields(model: string): NumericField[] {
  if (!rtcpModels.some(item => item.value === model)) return []
  const offsets = model === 'xyzac-trt-kins' ? ['Y', 'Z'] : ['X', 'Z']
  return [
    ...['X', 'Y', 'Z'].map(axis => ({ key: 'center' + axis, label: '旋转中心 ' + axis, unit: 'mm' })),
    ...offsets.map(axis => ({ key: 'offset' + axis, label: '旋转轴偏置 ' + axis, unit: 'mm' })),
    { key: 'toolLength', label: '当前刀长补偿', unit: 'mm' },
  ]
}
