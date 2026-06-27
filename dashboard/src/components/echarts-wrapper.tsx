'use client';

import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';

interface Props {
  option: EChartsOption;
  className?: string;
  style?: React.CSSProperties;
}

export default function EChartsWrapper({ option, className, style }: Props) {
  return (
    <ReactECharts
      option={option}
      className={className}
      style={{ height: 400, ...style }}
      notMerge
      lazyUpdate
    />
  );
}
