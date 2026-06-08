import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { accessApi } from '../lib/api';
import { PageHeader, Card, Button, Badge, Table, Empty } from '../components/ui';

export default function AccessPage() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ['access'], queryFn: accessApi.list });
  const review = useMutation({ mutationFn: ({ id, decision }: any) => accessApi.review(id, { decision }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['access'] }) });
  return (
    <div>
      <PageHeader title="Access Requests" subtitle="Request and approve scoped, time-bound access to assets" />
      <Card className="p-5">
        {data?.length ? (
          <Table head={['Purpose', 'Access', 'Assets', 'Status', 'Decision']}>
            {data.map((r: any) => (
              <tr key={r.id} className="border-b border-slate-100">
                <td className="py-2 px-3">{r.purpose}</td>
                <td className="py-2 px-3"><Badge>{r.access_type}</Badge></td>
                <td className="py-2 px-3">{r.asset_ids?.length ?? 0}</td>
                <td className="py-2 px-3"><Badge>{r.status}</Badge></td>
                <td className="py-2 px-3 flex gap-2">
                  {r.status === 'pending' && <>
                    <Button onClick={() => review.mutate({ id: r.id, decision: 'approved' })}>Approve</Button>
                    <Button variant="danger" onClick={() => review.mutate({ id: r.id, decision: 'rejected' })}>Reject</Button>
                  </>}
                </td>
              </tr>
            ))}
          </Table>
        ) : <Empty message="No access requests yet." />}
      </Card>
    </div>
  );
}
