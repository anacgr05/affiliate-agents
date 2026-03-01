"use client";
import { useEffect, useState, useRef } from 'react';
import ReactMarkdown from 'react-markdown';

export default function Dashboard() {
    const [logs, setLogs] = useState<any[]>([]);
    const [status, setStatus] = useState("IDLE");
    const [topic, setTopic] = useState("");
    const [plan, setPlan] = useState<any>(null);
    const [comment, setComment] = useState("");
    const [memory, setMemory] = useState("");
    const [posts, setPosts] = useState<any[]>([]);
    const [serverLogs, setServerLogs] = useState<string[]>([]);
    const [recommendations, setRecommendations] = useState<any[]>([]);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const logsEndRef = useRef<HTMLDivElement>(null);
    const serverLogsEndRef = useRef<HTMLDivElement>(null);

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

    const fetchExtras = async () => {
        try {
            const memRes = await fetch('http://localhost:8000/agent/memory');
            const memData = await memRes.json();
            setMemory(memData.memory);

            const postsRes = await fetch('http://localhost:8000/agent/posts');
            const postsData = await postsRes.json();
            setPosts(postsData.posts);

            const logsRes = await fetch('http://localhost:8000/agent/logs');
            const logsData = await logsRes.json();
            setServerLogs(logsData.logs || []);
        } catch (e) {
            console.error("Failed to fetch extras", e);
        }
    };

    useEffect(() => {
        const interval = setInterval(() => {
            fetchStatus();
            fetchExtras();
        }, 3000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [logs.length]);

    useEffect(() => {
        serverLogsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [serverLogs.length]);

    const startAgent = async () => {
        if (!topic) return;
        await fetch('http://localhost:8000/agent/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic }),
        });
        setTopic("");
    };

    const runAnalysis = async () => {
        setIsAnalyzing(true);
        try {
            const res = await fetch('http://localhost:8000/agent/analyze', { method: 'POST' });
            const data = await res.json();
            setRecommendations(data.recommendations || []);
        } catch (e) {
            console.error("Analysis failed", e);
        }
        setIsAnalyzing(false);
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
        <main className="min-h-screen bg-gray-50 text-gray-900 p-8 font-sans">
            <header className="mb-8 flex justify-between items-center border-b border-gray-200 pb-4">
                <h1 className="text-3xl font-bold text-blue-600">🤖 Agent Command Center</h1>
                <div className="flex items-center gap-2 bg-white px-3 py-1 rounded-full border border-gray-300 shadow-sm">
                    <span className={`w-3 h-3 rounded-full ${status === 'PROCESSING' ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`}></span>
                    <span className="text-sm font-mono text-gray-600">{status}</span>
                </div>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 h-[calc(100vh-140px)]">
                {/* Main Content Area (Chat + Terminal) */}
                <div className="lg:col-span-2 flex flex-col gap-6 h-full">
                    {/* Live Logs */}
                    <div className="flex-1 border border-gray-200 rounded-xl p-6 bg-white flex flex-col shadow-sm min-h-0">
                        <h2 className="text-xl font-semibold mb-4 border-b border-gray-100 pb-2 text-gray-800">Live Conversation</h2>
                        <div className="flex-1 overflow-y-auto space-y-4 pr-2 scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent">
                            {logs.map((msg, i) => (
                                <div key={i} className={`p-4 rounded-lg ${msg.role === 'human' ? 'bg-blue-50 border border-blue-100' : 'bg-gray-50 border border-gray-100'}`}>
                                    <strong className="block text-xs uppercase text-gray-500 mb-1">{msg.role}</strong>
                                    <div className="prose prose-sm max-w-none text-gray-800 break-words overflow-x-auto">
                                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                                    </div>
                                </div>
                            ))}
                            <div ref={logsEndRef} />
                        </div>
                    </div>

                    {/* Backend Terminal */}
                    <div className="border border-gray-200 rounded-xl p-6 bg-gray-900 text-green-400 flex flex-col shadow-sm font-mono text-xs h-48 shrink-0">
                        <h2 className="text-sm font-bold mb-2 text-gray-400 border-b border-gray-700 pb-1">Backend Terminal Output</h2>
                        <div className="flex-1 overflow-y-auto space-y-1">
                            {serverLogs.map((log, i) => (
                                <div key={i} className="break-words">
                                    <span className="text-gray-500 mr-2">{log.split(' - ')[0]}</span>
                                    <span>{log.split(' - ').slice(1).join(' - ')}</span>
                                </div>
                            ))}
                            <div ref={serverLogsEndRef} />
                        </div>
                    </div>
                </div>

                {/* Sidebar Controls */}
                <div className="space-y-6 h-full overflow-y-auto pr-2">
                    {/* Start Panel */}
                    <div className="border border-gray-200 rounded-xl p-6 bg-white shadow-sm">
                        <h2 className="text-xl font-semibold mb-4 text-gray-800">New Mission</h2>
                        <div className="flex gap-2">
                            <input
                                type="text"
                                value={topic}
                                onChange={(e) => setTopic(e.target.value)}
                                placeholder="Enter topic (e.g. Best Gaming Mouse)"
                                className="flex-1 bg-white border border-gray-300 rounded px-3 py-2 text-gray-900 focus:outline-none focus:border-blue-500 placeholder-gray-400"
                            />
                            <button
                                onClick={startAgent}
                                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded font-medium transition-colors shadow-sm"
                            >
                                Start
                            </button>
                        </div>
                    </div>

                    {/* Analyst Insights */}
                    <div className="border border-purple-200 rounded-xl p-6 bg-purple-50 shadow-sm">
                        <div className="flex justify-between items-center mb-4">
                            <h2 className="text-xl font-semibold text-purple-800">🔮 Analyst Insights</h2>
                            <button
                                onClick={runAnalysis}
                                disabled={isAnalyzing}
                                className="text-xs bg-purple-600 text-white px-3 py-1 rounded hover:bg-purple-700 disabled:opacity-50 transition-colors"
                            >
                                {isAnalyzing ? 'Analyzing...' : 'Auto-Analyze'}
                            </button>
                        </div>

                        {recommendations.length > 0 ? (
                            <div className="space-y-3">
                                {recommendations.map((rec, i) => (
                                    <div key={i} className="bg-white p-3 rounded border border-purple-100 hover:border-purple-300 cursor-pointer transition-colors group" onClick={() => setTopic(rec.topic)}>
                                        <div className="flex justify-between items-start">
                                            <h3 className="font-medium text-purple-900 group-hover:text-purple-700">{rec.topic}</h3>
                                            <span className="text-xs text-purple-400 opacity-0 group-hover:opacity-100 transition-opacity">Click to use</span>
                                        </div>
                                        <p className="text-xs text-purple-600 mt-1">{rec.reason}</p>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-sm text-purple-400 italic">Run analysis to find content gaps.</p>
                        )}
                    </div>

                    {/* Approval Panel */}
                    {status === 'WAITING_FOR_APPROVAL' && plan && (
                        <div className="border border-yellow-200 rounded-xl p-6 bg-yellow-50 animate-in fade-in slide-in-from-bottom-4 shadow-sm">
                            <h2 className="text-xl font-semibold mb-4 text-yellow-700">⚠️ Approval Required</h2>

                            <div className="bg-white p-4 rounded mb-4 text-sm border border-gray-200 text-gray-700">
                                <p><strong className="text-gray-900">Topic:</strong> {plan.topic}</p>
                                <p><strong className="text-gray-900">Angle:</strong> {plan.angle}</p>
                                <p><strong className="text-gray-900">Products:</strong> {plan.key_products?.length}</p>
                            </div>

                            <div className="space-y-3">
                                <textarea
                                    value={comment}
                                    onChange={(e) => setComment(e.target.value)}
                                    placeholder="Feedback (if rejecting)..."
                                    className="w-full bg-white border border-gray-300 rounded px-3 py-2 text-gray-900 text-sm focus:outline-none focus:border-yellow-500 placeholder-gray-400"
                                    rows={3}
                                />
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => sendFeedback(false)}
                                        className="flex-1 bg-red-100 hover:bg-red-200 text-red-700 border border-red-200 px-4 py-2 rounded font-medium transition-colors"
                                    >
                                        Reject
                                    </button>
                                    <button
                                        onClick={() => sendFeedback(true)}
                                        className="flex-1 bg-green-100 hover:bg-green-200 text-green-700 border border-green-200 px-4 py-2 rounded font-medium transition-colors"
                                    >
                                        Approve
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                    {status === 'IDLE' && (
                        <div className="text-center text-gray-400 mt-10 p-4 border border-dashed border-gray-200 rounded-lg">
                            <p>System Ready. Waiting for input.</p>
                        </div>
                    )}

                    {/* Memory Bank */}
                    <div className="border border-gray-200 rounded-xl p-6 bg-white shadow-sm">
                        <h2 className="text-xl font-semibold mb-4 text-gray-800">🧠 Memory Bank</h2>
                        <div className="bg-gray-50 p-4 rounded border border-gray-100 text-sm text-gray-600 max-h-40 overflow-y-auto">
                            {memory ? (
                                <p className="whitespace-pre-wrap">{memory}</p>
                            ) : (
                                <p className="italic">No memories found yet.</p>
                            )}
                        </div>
                    </div>

                    {/* Recent Drafts */}
                    <div className="border border-gray-200 rounded-xl p-6 bg-white shadow-sm">
                        <h2 className="text-xl font-semibold mb-4 text-gray-800">📄 Recent Drafts</h2>
                        <div className="space-y-2">
                            {posts.length > 0 ? posts.slice(-3).reverse().map((post, i) => (
                                <div key={i} className="p-3 bg-gray-50 rounded border border-gray-100">
                                    <p className="font-medium text-gray-900 truncate">{post.title}</p>
                                    <p className="text-xs text-gray-500">{post.slug}</p>
                                </div>
                            )) : (
                                <p className="text-sm text-gray-500 italic">No drafts created yet.</p>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </main>
    );
}
