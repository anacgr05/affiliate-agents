"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type Post = {
  slug: string;
  title: string;
  excerpt: string;
  hero?: { title: string; subtitle: string; image: string };
  image_url?: string | null;
  image_status?: string | null;
};

export default function Home() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/agent/posts")
      .then((r) => r.json())
      .then(({ posts }: { posts: Post[] }) => {
        setPosts(posts ?? []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Hero Section */}
      <div className="bg-white border-b border-gray-200 py-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-5xl font-bold tracking-tight text-gray-900 mb-6">
            Reviews que <span className="text-blue-600">Funcionam</span>
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Análises detalhadas, imparciais e diretas ao ponto para ajudar você a fazer a melhor escolha.
          </p>
        </div>
      </div>

      {/* Content Grid */}
      <div className="max-w-7xl mx-auto px-6 py-16">
        <h2 className="text-2xl font-bold text-gray-900 mb-8">Últimas Análises</h2>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="bg-white rounded-2xl border border-gray-200 overflow-hidden animate-pulse">
                <div className="h-48 bg-gray-200" />
                <div className="p-6 space-y-3">
                  <div className="h-3 bg-gray-200 rounded w-1/3" />
                  <div className="h-5 bg-gray-200 rounded" />
                  <div className="h-4 bg-gray-200 rounded w-5/6" />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {posts.map((post) => {
              const thumbUrl =
                post.image_status === "ready" && post.image_url
                  ? post.image_url
                  : post.hero?.image ?? null;

              return (
                <Link href={`/reviews/${post.slug}`} key={post.slug} className="group">
                  <div className="h-full bg-white rounded-2xl border border-gray-200 overflow-hidden hover:shadow-lg transition-all duration-300 hover:-translate-y-1">
                    <div className="h-48 bg-gray-100 relative overflow-hidden">
                      {thumbUrl && !thumbUrl.includes("placehold") ? (
                        <img
                          src={thumbUrl}
                          alt={post.title}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
                          <span className="text-4xl">📱</span>
                        </div>
                      )}
                    </div>
                    <div className="p-6">
                      <div className="flex items-center gap-2 mb-3">
                        <span className="bg-blue-100 text-blue-700 text-xs font-bold px-2 py-1 rounded-full uppercase tracking-wide">
                          Review
                        </span>
                        <span className="text-gray-400 text-xs">5 min de leitura</span>
                      </div>
                      <h3 className="text-xl font-bold text-gray-900 mb-3 group-hover:text-blue-600 transition-colors line-clamp-2">
                        {post.title}
                      </h3>
                      <p className="text-gray-600 text-sm line-clamp-3 mb-4">
                        {post.excerpt}
                      </p>
                      <div className="flex items-center text-blue-600 font-medium text-sm">
                        Ler Análise Completa
                        <svg className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
                        </svg>
                      </div>
                    </div>
                  </div>
                </Link>
              );
            })}

            {!loading && posts.length === 0 && (
              <div className="col-span-full text-center py-20 bg-white rounded-2xl border border-dashed border-gray-300">
                <div className="text-gray-400 mb-4 text-4xl">🤖</div>
                <h3 className="text-lg font-medium text-gray-900">Nenhum review gerado ainda</h3>
                <p className="text-gray-500">Vá ao Dashboard para criar seu primeiro conteúdo.</p>
                <Link href="/admin/dashboard" className="inline-block mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                  Ir para Dashboard
                </Link>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
