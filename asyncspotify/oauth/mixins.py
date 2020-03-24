import asyncio
import logging

from ..http import Route

log = logging.getLogger(__name__)


class RefreshableFlowMixin:
	_task: asyncio.Task = None

	async def refresh(self, start_task=True):
		'''Refresh this authenticator.'''

		meth = getattr(self, 'token', None)

		if not callable(meth):
			raise ValueError('This authorizer does not support token refreshing')

		data = None

		try:
			data = await meth()
			self._data = data
			if hasattr(self, 'store'):
				await self.store(data)
		finally:
			if start_task:
				if data is None:
					raise RuntimeError('Can\'t restart token refresh task when previous refresh failed')
				self.refresh_in(data.seconds_until_expire())

	async def _token(self, data):
		data = await self.client.http.request(
			Route('POST', 'https://accounts.spotify.com/api/token'),
			data=data,
			authorize=False
		)

		# data['expires_in'] = 5

		return data

	def refresh_in(self, seconds, cancel_task=True):
		# cancel old task if it's running
		if cancel_task and self._task is not None:
			self._task.cancel()

		# and create new refresh task
		self._task = asyncio.create_task(self._refresh_in_meta(seconds))

	async def _refresh_in_meta(self, seconds):
		if seconds > 0:
			log.info('Refreshing access token in %s seconds', seconds)
			await asyncio.sleep(seconds)
			log.debug('Refreshing access token now', seconds)

		await self.refresh(start_task=False)
		self.refresh_in(self._data.seconds_until_expire(), cancel_task=False)

	async def close(self):
		if self._task is not None:
			self._task.cancel()
			await self._task
