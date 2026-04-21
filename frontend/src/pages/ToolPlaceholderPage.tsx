import { Card, CardDesc, CardHeader, CardTitle } from '../components/ui/Card'

export default function ToolPlaceholderPage(props: { title: string; desc: string }) {
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>{props.title}</CardTitle>
          <CardDesc>{props.desc}</CardDesc>
        </CardHeader>
        <div className="text-sm leading-relaxed text-text-secondary">
          This tool page is under construction.
        </div>
      </Card>
    </div>
  )
}
