import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface CVE {
    cves: string[];
    severity: string;
    advisory_id: string;
    raw_text: string;
}

interface PathOption {
    version: string;
    type: string;
    residual_risk_percent: number;
    resolves: CVE[];
    risks_waiting: CVE[];
    description: string;
}

interface UpgradeAdvisorData {
    current_version: string;
    current_risk_percent: number;
    current_cves: CVE[];
    best_upgrade: string;
    paths: Record<string, PathOption>;
}

interface Cluster {
    id: string;
    name: string;
    current_version: string;
    risk_percent: number;
}

const RiskGauge = ({ percent, size = 'lg' }: { percent: number, size?: 'sm' | 'lg' }) => {
    const radius = size === 'lg' ? 40 : 20;
    const stroke = size === 'lg' ? 8 : 4;
    const normalizedRadius = radius - stroke * 2;
    const circumference = normalizedRadius * 2 * Math.PI;
    const strokeDashoffset = circumference - (percent / 100) * circumference;

    let color = 'text-emerald-500';
    if (percent > 30) color = 'text-amber-500';
    if (percent > 70) color = 'text-rose-500';

    return (
        <div className="relative flex items-center justify-center">
            <svg height={radius * 2} width={radius * 2} className="transform -rotate-90">
                <circle
                    stroke="currentColor"
                    fill="transparent"
                    strokeWidth={stroke}
                    r={normalizedRadius}
                    cx={radius}
                    cy={radius}
                    className="text-slate-700"
                />
                <circle
                    stroke="currentColor"
                    fill="transparent"
                    strokeWidth={stroke}
                    strokeDasharray={circumference + ' ' + circumference}
                    style={{ strokeDashoffset }}
                    r={normalizedRadius}
                    cx={radius}
                    cy={radius}
                    className={`${color} transition-all duration-1000 ease-out`}
                />
            </svg>
            <div className={`absolute font-bold font-mono ${size === 'lg' ? 'text-2xl' : 'text-sm'} ${color}`}>
                {percent}%
            </div>
        </div>
    );
};

const CVEList = ({ cves, emptyMsg }: { cves: CVE[], emptyMsg: string }) => {
    if (cves.length === 0) return <p className="text-sm text-slate-500 italic py-2">{emptyMsg}</p>;
    
    return (
        <div className="space-y-2 mt-2 max-h-48 overflow-y-auto pr-2 custom-scrollbar">
            {cves.map((cve, idx) => (
                <div key={idx} className="bg-slate-900/50 p-2.5 rounded-lg border border-slate-700/50 hover:border-slate-600 transition-colors">
                    <div className="flex justify-between items-center mb-1">
                        <span className="font-mono text-xs text-blue-300 font-bold">{cve.advisory_id}</span>
                        <span className={`text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded ${
                            cve.severity === 'Critical' ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' :
                            cve.severity === 'Important' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                            'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                        }`}>
                            {cve.severity}
                        </span>
                    </div>
                    <p className="text-xs text-slate-400 line-clamp-2" title={cve.raw_text}>{cve.raw_text}</p>
                </div>
            ))}
        </div>
    );
};

const UpgradeAdvisor = () => {
    const [clusters, setClusters] = useState<Cluster[]>([]);
    const [selectedCluster, setSelectedCluster] = useState<string | null>(null);
    const [advisorData, setAdvisorData] = useState<UpgradeAdvisorData | null>(null);
    const [loading, setLoading] = useState<boolean>(false);
    const [activeTabs, setActiveTabs] = useState<Record<string, 'resolves'|'waiting'>>({});

    useEffect(() => {
        axios.get('http://localhost:8000/api/clusters')
            .then(res => setClusters(res.data))
            .catch(err => console.error("Error fetching clusters:", err));
    }, []);

    const fetchAdvisorData = async (clusterId: string) => {
        setSelectedCluster(clusterId);
        setLoading(true);
        try {
            const res = await axios.get(`http://localhost:8000/api/clusters/${clusterId}/upgrade-advisor`);
            setAdvisorData(res.data);
            
            // Default tabs to 'resolves'
            const tabs: Record<string, 'resolves'|'waiting'> = {};
            Object.keys(res.data.paths).forEach(v => tabs[v] = 'resolves');
            setActiveTabs(tabs);
        } catch (error) {
            console.error("Error fetching advisor data:", error);
        } finally {
            setLoading(false);
        }
    };

    const toggleTab = (version: string, tab: 'resolves' | 'waiting') => {
        setActiveTabs(prev => ({ ...prev, [version]: tab }));
    };

    return (
        <div className="p-8 min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-blue-500/30">
            <h1 className="text-4xl font-extrabold mb-8 bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent">
                Advanced Upgrade Advisor
            </h1>
            
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
                {/* Cluster Sidebar */}
                <div className="lg:col-span-1 space-y-6">
                    <div className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-slate-800 shadow-2xl p-6">
                        <h2 className="text-lg font-bold mb-4 text-slate-200 flex items-center gap-2">
                            <span>🏢</span> Your Clusters
                        </h2>
                        {clusters.length === 0 ? (
                            <p className="text-slate-500 text-sm">No clusters found.</p>
                        ) : (
                            <div className="space-y-3">
                                {clusters.map(cluster => (
                                    <div 
                                        key={cluster.id} 
                                        onClick={() => fetchAdvisorData(cluster.id)}
                                        className={`p-4 rounded-xl cursor-pointer transition-all duration-300 border relative overflow-hidden group ${
                                            selectedCluster === cluster.id 
                                                ? 'bg-blue-600/10 border-blue-500/50 shadow-[0_0_20px_rgba(59,130,246,0.15)]' 
                                                : 'bg-slate-800/40 border-transparent hover:bg-slate-800'
                                        }`}
                                    >
                                        <div className="flex justify-between items-start">
                                            <div>
                                                <div className="font-semibold text-md text-slate-200">{cluster.name}</div>
                                                <div className="text-xs text-slate-500 mt-1 font-mono">v{cluster.current_version}</div>
                                            </div>
                                            <div className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wider ${
                                                cluster.risk_percent > 70 ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' :
                                                cluster.risk_percent > 30 ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                                                'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                            }`}>
                                                {cluster.risk_percent}% RISK
                                            </div>
                                        </div>
                                        {selectedCluster === cluster.id && (
                                            <div className="absolute inset-y-0 right-0 w-1 bg-blue-500 rounded-l-full shadow-[0_0_10px_rgba(59,130,246,0.8)]"></div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* Advisor Workspace */}
                <div className="lg:col-span-3">
                    {loading && (
                        <div className="flex flex-col items-center justify-center h-64 gap-4">
                            <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                            <p className="text-slate-400 font-medium animate-pulse">Calculating errata risk vectors...</p>
                        </div>
                    )}
                    
                    {!loading && advisorData && (
                        <div className="space-y-8 animate-fade-in-up">
                            
                            {/* Current Posture Header */}
                            <div className="bg-slate-900/60 backdrop-blur-md rounded-3xl border border-slate-800 p-8 shadow-2xl flex flex-col md:flex-row items-center justify-between gap-8">
                                <div>
                                    <h2 className="text-xs uppercase tracking-widest text-slate-500 font-bold mb-1">Current Posture</h2>
                                    <div className="text-4xl font-mono font-bold text-slate-200 mb-2">v{advisorData.current_version}</div>
                                    <p className="text-sm text-slate-400 max-w-md">
                                        You currently have <span className="text-rose-400 font-bold">{advisorData.current_cves.length} active vulnerabilities</span> impacting this cluster version.
                                    </p>
                                </div>
                                <div className="flex flex-col items-center bg-slate-950/50 p-6 rounded-2xl border border-slate-800/50 shadow-inner">
                                    <RiskGauge percent={advisorData.current_risk_percent} size="lg" />
                                    <span className="text-xs font-bold text-slate-500 uppercase tracking-widest mt-3">Risk Index</span>
                                </div>
                            </div>

                            {/* Upgrade Target Cards */}
                            <div>
                                <h3 className="text-xl font-bold text-slate-300 mb-4 flex items-center gap-2">
                                    <span>🚀</span> Available Upgrade Paths
                                </h3>
                                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                                    {Object.values(advisorData.paths).map((path) => {
                                        const isBest = path.version === advisorData.best_upgrade;
                                        const activeTab = activeTabs[path.version] || 'resolves';
                                        
                                        return (
                                            <div key={path.version} className={`relative flex flex-col bg-slate-900/40 backdrop-blur-xl border rounded-3xl p-6 shadow-xl transition-all duration-500 hover:-translate-y-1 ${
                                                isBest 
                                                ? 'border-emerald-500/50 shadow-[0_10px_30px_rgba(16,185,129,0.1)]' 
                                                : 'border-slate-700/50 hover:border-slate-600'
                                            }`}>
                                                {isBest && (
                                                    <div className="absolute -top-3 -right-3 bg-gradient-to-r from-emerald-400 to-teal-500 text-slate-950 text-xs font-extrabold uppercase tracking-widest px-4 py-1.5 rounded-full shadow-lg border border-emerald-300 flex items-center gap-1 animate-pulse-slow">
                                                        <span>⭐</span> Best Choice
                                                    </div>
                                                )}
                                                
                                                <div className="flex justify-between items-start mb-6">
                                                    <div>
                                                        <div className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-1">{path.type} Target</div>
                                                        <div className={`text-3xl font-mono font-bold ${isBest ? 'text-emerald-400' : 'text-slate-300'}`}>
                                                            v{path.version}
                                                        </div>
                                                    </div>
                                                    <div className="flex flex-col items-center">
                                                        <RiskGauge percent={path.residual_risk_percent} size="sm" />
                                                        <span className="text-[9px] text-slate-500 uppercase tracking-wider font-bold mt-1">Residual</span>
                                                    </div>
                                                </div>

                                                {/* Tabs */}
                                                <div className="flex border-b border-slate-800 mb-3">
                                                    <button 
                                                        onClick={() => toggleTab(path.version, 'resolves')}
                                                        className={`flex-1 pb-2 text-xs font-bold uppercase tracking-widest transition-colors ${activeTab === 'resolves' ? 'text-emerald-400 border-b-2 border-emerald-400' : 'text-slate-500 hover:text-slate-400'}`}
                                                    >
                                                        Resolves ({path.resolves.length})
                                                    </button>
                                                    <button 
                                                        onClick={() => toggleTab(path.version, 'waiting')}
                                                        className={`flex-1 pb-2 text-xs font-bold uppercase tracking-widest transition-colors ${activeTab === 'waiting' ? 'text-amber-400 border-b-2 border-amber-400' : 'text-slate-500 hover:text-slate-400'}`}
                                                    >
                                                        Waiting ({path.risks_waiting.length})
                                                    </button>
                                                </div>

                                                <div className="flex-1 min-h-[200px]">
                                                    {activeTab === 'resolves' ? (
                                                        <CVEList cves={path.resolves} emptyMsg="No existing vulnerabilities resolved by this upgrade." />
                                                    ) : (
                                                        <CVEList cves={path.risks_waiting} emptyMsg="No known residual vulnerabilities in this version." />
                                                    )}
                                                </div>
                                                
                                                <button className={`mt-6 w-full py-3.5 rounded-xl font-bold text-sm tracking-wide transition-all shadow-lg ${
                                                    isBest 
                                                    ? 'bg-emerald-500 hover:bg-emerald-400 text-emerald-950 shadow-emerald-500/20' 
                                                    : 'bg-slate-800 hover:bg-slate-700 text-slate-300 shadow-transparent'
                                                }`}>
                                                    Execute Upgrade to {path.version}
                                                </button>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
            
            {/* Custom Styles */}
            <style dangerouslySetInnerHTML={{__html: `
                @keyframes fadeInUp {
                    from { opacity: 0; transform: translateY(15px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                .animate-fade-in-up {
                    animation: fadeInUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                }
                @keyframes pulseSlow {
                    0%, 100% { transform: scale(1); }
                    50% { transform: scale(1.05); }
                }
                .animate-pulse-slow {
                    animation: pulseSlow 3s ease-in-out infinite;
                }
                .custom-scrollbar::-webkit-scrollbar {
                    width: 4px;
                }
                .custom-scrollbar::-webkit-scrollbar-track {
                    background: transparent; 
                }
                .custom-scrollbar::-webkit-scrollbar-thumb {
                    background: #334155; 
                    border-radius: 4px;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                    background: #475569; 
                }
            `}} />
        </div>
    );
};

export default UpgradeAdvisor;
