"use client";
import { useEffect, useState, useRef } from 'react';
import ReactMarkdown from 'react-markdown';

export default function Dashboard() {
    const [logs, setLogs] = useState<any[]>([]);
    const [status, setStatus] = useState("IDLE");
    const [topic, setTopic] = useState("");
    const [plan, setPlan] = useState<any>(null);
    const [comment, setComment] = useState("");
    const logsEndRef = useRef<HTMLDivElement>(null);

    const fetchStatus = async () => {
        try {
            const res = await fetch('http://localhost:8000/agent/status');
            const data = await res.json();
            setLogs(data.messages || []);
            setStatus(data.status);
            setPlan(data.plan);
        } catch (e) {
            console.error("Failed to fetch status", e);
        }
    };

    useEffect(() => {
        const interval = setInterval(fetchStatus, 1000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [logs]);

    const startAgent = async () => {
        if (!topic) return;
        await fetch('http://localhost:8000/agent/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic }),
        });
        setTopic("");
    };

    const sendFeedback = async (approved: boolean) => {
        await fetch('http://localhost:8000/agent/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ approved, comments: comment }),
        });
        setComment("");
    };

    return (
        <main className="min-h-screen bg-black text-white p-8 font-sans">
            <header className="mb-8 flex justify-between items-center">
                <h1 className="text-3xl font-bold text-blue-500">🤖 Agent Command Center</h1>
                <div className="flex items-center gap-2">
                    <span className={`w-3 h-3 rounded-full ${status === 'PROCESSING' ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`}></span>
                    <span className="text-sm font-mono text-gray-400">{status}</span>
                </div>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 h-[80vh]">
                {/* Live Logs */}
                <div className="lg:col-span-2 border border-gray-800 rounded-xl p-6 bg-gray-900/50 flex flex-col">
                    <h2 className="text-xl font-semibold mb-4 border-b border-gray-700 pb-2">Live Conversation</h2>
                    <div className="flex-1 overflow-y-auto space-y-4 pr-2">
                        {logs.map((msg, i) => (
                            <div key={i} className={`p-4 rounded-lg ${msg.role === 'human' ? 'bg-blue-900/20 border border-blue-800' : 'bg-gray-800/50 border border-gray-700'}`}>
                                <strong className="block text-xs uppercase text-gray-500 mb-1">{msg.role}</strong>
                                <div className="prose prose-invert prose-sm max-w-none">
                                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                                </div>
                            </div>
                        ))}
                        <div ref={logsEndRef} />
                    </div>
                </div>

                {/* Controls */}
                <div className="space-y-6">
                    {/* Start Panel */}
                    <div className="border border-gray-800 rounded-xl p-6 bg-gray-900/50">
                        <h2 className="text-xl font-semibold mb-4">New Mission</h2>
                        <div className="flex gap-2">
                            <input
                                type="text"
                                value={topic}
                                onChange={(e) => setTopic(e.target.value)}
                                placeholder="Enter topic (e.g. Best Gaming Mouse)"
                                className="flex-1 bg-black border border-gray-700 rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                            />
                            <button
                                onClick={startAgent}
                                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded font-medium transition-colors"
                            >
                                Start
                            </button>
                        </div>
                    </div>

                    {/* Approval Panel */}
                    {status === 'WAITING_FOR_APPROVAL' && plan && (
                        <div className="border border-yellow-500/30 rounded-xl p-6 bg-yellow-900/10 animate-in fade-in slide-in-from-bottom-4">
                            <h2 className="text-xl font-semibold mb-4 text-yellow-500">⚠️ Approval Required</h2>

                            <div className="bg-black/50 p-4 rounded mb-4 text-sm border border-gray-800">
                                <p><strong>Topic:</strong> {plan.topic}</p>
                                <p><strong>Angle:</strong> {plan.angle}</p>
                                <p><strong>Products:</strong> {plan.key_products?.length}</p>
                            </div>

                            <div className="space-y-3">
                                <textarea
                                    value={comment}
                                    onChange={(e) => setComment(e.target.value)}
                                    placeholder="Feedback (if rejecting)..."
                                    className="w-full bg-black border border-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-yellow-500"
                                    rows={3}
                                />
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => sendFeedback(false)}
                                        className="flex-1 bg-red-900/50 hover:bg-red-900 text-red-200 border border-red-800 px-4 py-2 rounded font-medium transition-colors"
                                    >
                                        Reject
                                    </button>
                                    <button
                                        onClick={() => sendFeedback(true)}
                                        className="flex-1 bg-green-900/50 hover:bg-green-900 text-green-200 border border-green-800 px-4 py-2 rounded font-medium transition-colors"
                                    >
                                        Approve
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                    {status === 'IDLE' && (
                        <div className="text-center text-gray-600 mt-10">
                            <p>System Ready.</p>
                        </div>
                    )}
                </div>
            </div>
        </main>
    );
}
