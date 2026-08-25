import { render } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { SkeletonCard } from "@/components/ui/SkeletonCard"

describe("SkeletonCard Component", () => {
  it("renders with default count of 1", () => {
    const { container } = render(<SkeletonCard />)
    const skeletons = container.querySelectorAll(".animate-pulse")
    expect(skeletons.length).toBe(1)
  })

  it("renders multiple skeletons with count prop", () => {
    const { container } = render(<SkeletonCard count={3} />)
    const skeletons = container.querySelectorAll(".animate-pulse")
    expect(skeletons.length).toBe(3)
  })

  it("applies custom className", () => {
    const { container } = render(<SkeletonCard className="custom-class" />)
    const skeleton = container.querySelector(".custom-class")
    expect(skeleton).toBeInTheDocument()
  })
})
