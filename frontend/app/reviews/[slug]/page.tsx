import { getPosts } from "@/lib/posts";
import Link from "next/link";
import { notFound } from "next/navigation";

export async function generateStaticParams() {
    const posts = getPosts();
    return posts.map((post) => ({
        slug: post.slug,
    }));
}

export default async function ReviewPage({ params }: { params: Promise<{ slug: string }> }) {
    const { slug } = await params;
    console.log("🔍 ReviewPage rendering for slug:", slug);
    const posts = getPosts();
    console.log(`📊 Found ${posts.length} posts available.`);
    const post = posts.find((p) => p.slug === slug);
    console.log("📝 Post found:", post ? "YES" : "NO");

    // if (!post) {
    //     notFound();
    // }

    // Handle legacy posts that don't have the new structure
    if (!post || !post.hero) {
        return (
            <div className="min-h-screen p-8 text-center">
                {/* DEBUG SECTION */}
                <div className="bg-red-100 p-4 border-b border-red-300 text-xs font-mono overflow-auto text-left mb-8">
                    <p className="font-bold text-red-700">DEBUG INFO (POST NOT FOUND OR LEGACY):</p>
                    <p>Requested Slug: {slug}</p>
                    <p>Total Posts Loaded: {posts.length}</p>
                    <p>Available Slugs:</p>
                    <ul className="list-disc pl-4">
                        {posts.map(p => <li key={p.slug}>{p.slug}</li>)}
                    </ul>
                </div>

                <h1 className="text-2xl font-bold mb-4">{post ? "Legacy Post Format" : "Post Not Found"}</h1>
                <p>This post was generated before the update. <Link href="/" className="text-blue-500">Go Back</Link></p>
                {post && (
                    <div className="mt-8 text-left max-w-2xl mx-auto prose dark:prose-invert">
                        <h1>{post.title}</h1>
                        <p>{post.excerpt}</p>
                        {/* Render raw content if available */}
                        <div className="whitespace-pre-wrap">{post.content}</div>
                    </div>
                )}
            </div>
        )
    }

    return (
        <main className="min-h-screen bg-white text-gray-900 font-sans">
            {/* Hero Section */}
            <section className="relative bg-gray-900 text-white py-20 px-6">
                <div className="max-w-4xl mx-auto text-center z-10 relative">
                    <span className="inline-block py-1 px-3 rounded-full bg-blue-600/20 border border-blue-500/30 text-blue-300 text-sm font-medium mb-6">
                        Review Completo 2026
                    </span>
                    <h1 className="text-4xl md:text-6xl font-bold mb-6 leading-tight">
                        {post.hero.title}
                    </h1>
                    <p className="text-xl text-gray-300 mb-8 max-w-2xl mx-auto">
                        {post.hero.subtitle}
                    </p>
                    <div className="text-sm text-gray-400">
                        Atualizado recentemente • Leitura de 5 min
                    </div>
                </div>
                {/* Abstract Background */}
                <div className="absolute inset-0 overflow-hidden opacity-20 pointer-events-none">
                    <div className="absolute top-[-50%] left-[-20%] w-[80%] h-[80%] rounded-full bg-blue-600 blur-[150px]" />
                    <div className="absolute bottom-[-50%] right-[-20%] w-[80%] h-[80%] rounded-full bg-purple-600 blur-[150px]" />
                </div>
            </section>

            <div className="max-w-4xl mx-auto px-6 py-12">

                {/* Quick Summary */}
                <div className="bg-blue-50 border border-blue-100 rounded-2xl p-8 mb-16">
                    <h3 className="text-blue-900 font-bold text-lg mb-3 flex items-center gap-2">
                        ⚡ Resumo Rápido
                    </h3>
                    <p className="text-blue-800 leading-relaxed">
                        {post.excerpt}
                    </p>
                </div>

                {/* Top Picks / Products */}
                <section className="mb-20">
                    <h2 className="text-3xl font-bold mb-10 text-center">Nossas Escolhas</h2>
                    <div className="space-y-8">
                        {post.products?.map((product: any, idx: number) => (
                            <div key={idx} className="border border-gray-200 rounded-2xl overflow-hidden shadow-sm hover:shadow-md transition-shadow bg-white">
                                <div className="p-6 md:p-8">
                                    <div className="flex flex-col md:flex-row justify-between items-start gap-4 mb-6">
                                        <div>
                                            <div className="flex items-center gap-2 mb-2">
                                                <span className="bg-gray-100 text-gray-600 px-2 py-1 rounded text-xs font-bold uppercase tracking-wider">
                                                    #{idx + 1}
                                                </span>
                                                {idx === 0 && (
                                                    <span className="bg-yellow-100 text-yellow-700 px-2 py-1 rounded text-xs font-bold uppercase tracking-wider flex items-center gap-1">
                                                        🏆 Melhor Escolha
                                                    </span>
                                                )}
                                            </div>
                                            <h3 className="text-2xl font-bold text-gray-900">{product.name}</h3>
                                            <div className="flex items-center gap-2 mt-2">
                                                <div className="flex text-yellow-400">
                                                    {"★".repeat(Math.floor(product.rating))}
                                                    {"☆".repeat(5 - Math.floor(product.rating))}
                                                </div>
                                                <span className="text-sm text-gray-500">({product.rating}/5.0)</span>
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <div className="text-sm text-gray-500 mb-1">Preço Aproximado</div>
                                            <div className="text-2xl font-bold text-green-600">{product.price}</div>
                                        </div>
                                    </div>

                                    <div className="grid md:grid-cols-2 gap-8 mb-6">
                                        <div>
                                            <h4 className="font-semibold text-green-700 mb-3 flex items-center gap-2">
                                                ✅ Prós
                                            </h4>
                                            <ul className="space-y-2">
                                                {product.pros.map((pro: string, i: number) => (
                                                    <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                                                        <span className="text-green-500 mt-0.5">✓</span>
                                                        {pro}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                        <div>
                                            <h4 className="font-semibold text-red-700 mb-3 flex items-center gap-2">
                                                ❌ Contras
                                            </h4>
                                            <ul className="space-y-2">
                                                {product.cons.map((con: string, i: number) => (
                                                    <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                                                        <span className="text-red-500 mt-0.5">•</span>
                                                        {con}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    </div>

                                    <div className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                                        <p className="text-sm text-gray-700 mb-3">
                                            <strong className="text-gray-900">Veredito:</strong> {product.verdict}
                                        </p>

                                        {/* Affiliate Links */}
                                        {product.affiliate_links && product.affiliate_links.length > 0 && (
                                            <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-gray-200">
                                                {product.affiliate_links.map((link: any, linkIdx: number) => (
                                                    <a
                                                        key={linkIdx}
                                                        href={link.url}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
                                                    >
                                                        🛒 Comprar na {link.store}
                                                        {link.price && <span className="opacity-90 text-xs border-l border-blue-500 pl-2 ml-1">{link.price}</span>}
                                                    </a>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </section>

                {/* Buying Guide */}
                <section className="mb-20">
                    <h2 className="text-3xl font-bold mb-10">Guia de Compra</h2>
                    <div className="space-y-12">
                        {post.buying_guide?.steps?.map((step: any, idx: number) => (
                            <div key={idx} className="flex gap-6">
                                <div className="flex-shrink-0 w-12 h-12 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center font-bold text-xl">
                                    {idx + 1}
                                </div>
                                <div>
                                    <h3 className="text-xl font-bold mb-3">{step.title}</h3>
                                    <p className="text-gray-600 leading-relaxed">{step.content}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </section>

                {/* FAQ */}
                <section className="mb-20 bg-gray-50 rounded-3xl p-8 md:p-12">
                    <h2 className="text-3xl font-bold mb-10 text-center">Perguntas Frequentes</h2>
                    <div className="space-y-6 max-w-3xl mx-auto">
                        {post.faq?.map((item: any, idx: number) => (
                            <div key={idx} className="bg-white rounded-xl p-6 shadow-sm">
                                <h3 className="font-bold text-lg mb-3 text-gray-900">{item.question}</h3>
                                <p className="text-gray-600">{item.answer}</p>
                            </div>
                        ))}
                    </div>
                </section>

            </div>
        </main>
    );
}
