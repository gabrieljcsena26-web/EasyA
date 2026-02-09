import React from 'react';

export default function MiniCalendar(){
	return (
		<div className="card mini-calendar">
			<div className="conf-section-title">Visão rápida · Janeiro 2026</div>
			<div className="conf-section-sub">Visão por dia · salão inteiro</div>
			<table>
				<thead>
					<tr><th>D</th><th>S</th><th>T</th><th>Q</th><th>Q</th><th>S</th><th>S</th></tr>
				</thead>
				<tbody>
					<tr>
						<td></td><td></td>
						<td><span className="day-pill day-busy">1</span></td>
						<td><span className="day-pill day-mid">2</span></td>
						<td><span className="day-pill day-busy">3</span></td>
						<td><span className="day-pill day-free">4</span></td>
						<td><span className="day-pill day-free">5</span></td>
					</tr>
					<tr>
						<td><span className="day-pill day-free">7</span></td>
						<td><span className="day-pill day-mid">8</span></td>
						<td><span className="day-pill day-selected">9</span></td>
						<td><span className="day-pill day-free">10</span></td>
						<td><span className="day-pill day-mid">11</span></td>
						<td><span className="day-pill day-busy">12</span></td>
						<td><span className="day-pill day-busy">13</span></td>
					</tr>
					<tr>
						<td><span className="day-pill day-free">14</span></td>
						<td><span className="day-pill day-free">15</span></td>
						<td><span className="day-pill day-mid">16</span></td>
						<td><span className="day-pill day-busy">17</span></td>
						<td><span className="day-pill day-busy">18</span></td>
						<td><span className="day-pill day-free">19</span></td>
						<td></td>
					</tr>
				</tbody>
			</table>
			<div className="legend">
				<span><span className="dot" style={{background:'#16a34a'}}></span>Poucos atendimentos</span>
				<span><span className="dot" style={{background:'#fbbf24'}}></span>Alguns atendimentos</span>
				<span><span className="dot" style={{background:'#f97373'}}></span>Muitos atendimentos</span>
			</div>
			<div className="calendar-status">Dia selecionado: <strong>09/01</strong> · 3 atendimentos no salão · <strong>alguns atendimentos</strong></div>
		</div>
	);
}
