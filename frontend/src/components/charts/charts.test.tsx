import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { Histogram } from './Histogram'
import { LineChart } from './LineChart'
import { niceTicks, spreadLabels } from './useWidth'

describe('chart helpers', () => {
  it('spreads colliding end labels apart and keeps them in bounds', () => {
    expect(spreadLabels([100, 100, 100], 13, 0, 200)).toEqual([100, 113, 126])
    expect(spreadLabels([195, 195], 13, 0, 200)).toEqual([187, 200])
    expect(spreadLabels([50, 10], 13, 0, 200)).toEqual([50, 10])
  })

  it('makes clean ticks', () => {
    expect(niceTicks(230)).toEqual([0, 100, 200, 300])
    expect(niceTicks(7)).toEqual([0, 2, 4, 6, 8])
    expect(niceTicks(0)).toEqual([0])
  })
})

describe('charts', () => {
  it('histogram renders bars with a hover tooltip', async () => {
    const user = userEvent.setup()
    const { container } = render(
      <Histogram data={{ '2': 3, '4': 1 }} label="Rounds" valueLabel={(v) => `${v} rounds`} />,
    )
    expect(screen.getByRole('img', { name: 'Rounds' })).toBeInTheDocument()
    expect(container.querySelectorAll('path')).toHaveLength(2) // the empty "3" column has no bar
    const targets = container.querySelectorAll('rect[fill="transparent"]')
    await user.hover(targets[0]!)
    expect(screen.getByRole('tooltip')).toHaveTextContent('2 rounds3 fights · 75.0%')
  })

  it('line chart shows a legend only for multiple series', () => {
    const one = [
      {
        key: 'a',
        label: 'Basic',
        points: [
          { x: 1, y: 1 },
          { x: 2, y: 0.5 },
        ],
      },
    ]
    const { rerender } = render(<LineChart series={one} label="Win rate" xLabel="Level" />)
    expect(screen.queryByRole('list', { name: 'Legend' })).not.toBeInTheDocument()
    rerender(
      <LineChart
        series={[
          ...one,
          {
            key: 'b',
            label: 'Medium',
            points: [
              { x: 1, y: 0.9 },
              { x: 2, y: 0.2 },
            ],
          },
        ]}
        label="Win rate"
        xLabel="Level"
      />,
    )
    expect(screen.getByRole('list', { name: 'Legend' })).toHaveTextContent('BasicMedium')
  })
})

describe('histogram binning', () => {
  it('groups very wide ranges instead of drawing thousands of bars', async () => {
    const user = userEvent.setup()
    const data = { '0': 5, '5000': 1, '9999': 2 }
    const { container } = render(
      <Histogram data={data} label="Damage" valueLabel={(v) => `${v} lost`} />,
    )
    expect(container.querySelectorAll('rect[fill="transparent"]').length).toBeLessThanOrEqual(60)
    await user.hover(container.querySelectorAll('rect[fill="transparent"]')[0]!)
    expect(screen.getByRole('tooltip')).toHaveTextContent('0 lost – 166 lost5 fights')
  })
})
