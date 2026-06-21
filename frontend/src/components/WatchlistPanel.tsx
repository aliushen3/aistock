import { useEffect, useState } from "react";
import { App as AntApp, Card, Space, Table, Tag, Typography } from "antd";
import { getWatchlist, type WatchlistItem } from "../lib/api";

const SOURCE_COLOR: Record<string, string> = {
  focus: "magenta",
  report_llm: "purple",
  report_rule: "geekblue",
  proposal: "orange",
  upload: "cyan",
  ods: "blue",
  ontology: "green",
};

interface Props {
  focus?: string;
  selectedSectorId?: string | null;
  onSelect?: (item: WatchlistItem) => void;
}

export default function WatchlistPanel({ focus, selectedSectorId, onSelect }: Props) {
  const { message } = AntApp.useApp();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<Awaited<ReturnType<typeof getWatchlist>> | null>(null);

  const load = () => {
    setLoading(true);
    getWatchlist(focus || undefined)
      .then(setData)
      .catch(() => message.error("加载动态观察清单失败"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [focus]);

  return (
    <Card
      title="动态观察清单（C7）"
      size="small"
      style={{ marginBottom: 16 }}
      extra={
        <Typography.Link onClick={load} disabled={loading}>
          刷新
        </Typography.Link>
      }
    >
      <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
        由研报主题、Ontology 赛道、ODS/上传元数据与待采纳提案自动合并，不再使用写死清单。
      </Typography.Paragraph>
      {data && (
        <Space wrap style={{ marginBottom: 12 }}>
          {Object.entries(data.source_counts).map(([source, count]) => (
            <Tag key={source} color={SOURCE_COLOR[source] || "default"}>
              {source}: {count}
            </Tag>
          ))}
          <Tag>研报主题 {data.report_themes.themes.length}</Tag>
        </Space>
      )}
      <Table
        size="small"
        loading={loading}
        rowKey={(row) => `${row.sector_name}:${row.source}`}
        pagination={{ pageSize: 6, hideOnSinglePage: true }}
        dataSource={data?.watchlist || []}
        rowClassName={(row) =>
          row.sector_id && row.sector_id === selectedSectorId ? "watchlist-row-selected" : ""
        }
        onRow={(row) => ({
          onClick: () => onSelect?.(row),
          style: { cursor: onSelect ? "pointer" : "default" },
        })}
        columns={[
          { title: "赛道", dataIndex: "sector_name", width: 140 },
          {
            title: "来源",
            dataIndex: "source",
            width: 110,
            render: (v: string) => <Tag color={SOURCE_COLOR[v] || "default"}>{v}</Tag>,
          },
          {
            title: "sector_id",
            dataIndex: "sector_id",
            render: (v: string | null) => v || "—",
          },
          {
            title: "关键词",
            dataIndex: "keywords",
            render: (v: string[]) => (
              <Typography.Text ellipsis={{ tooltip: v.join("、") }}>
                {(v || []).slice(0, 4).join("、")}
              </Typography.Text>
            ),
          },
        ]}
      />
    </Card>
  );
}
