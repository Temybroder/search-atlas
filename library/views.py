from rest_framework import viewsets, status
from rest_framework.response import Response
from django.db import models
from .models import Author, Book, Member, Loan
from .serializers import AuthorSerializer, BookSerializer, MemberSerializer, LoanSerializer
from rest_framework.decorators import action
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from .tasks import send_loan_notification

class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.select_related('author').all()
    serializer_class = BookSerializer

    @action(detail=True, methods=['post'])
    def loan(self, request, pk=None):
        book = self.get_object()
        if book.available_copies < 1:
            return Response({'error': 'No available copies.'}, status=status.HTTP_400_BAD_REQUEST)
        member_id = request.data.get('member_id')
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            return Response({'error': 'Member does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan = Loan.objects.create(book=book, member=member)
        book.available_copies -= 1
        book.save()
        send_loan_notification.delay(loan.id)
        return Response({'status': 'Book loaned successfully.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def return_book(self, request, pk=None):
        book = self.get_object()
        member_id = request.data.get('member_id')
        try:
            loan = Loan.objects.get(book=book, member__id=member_id, is_returned=False)
        except Loan.DoesNotExist:
            return Response({'error': 'Active loan does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan.is_returned = True
        loan.return_date = timezone.now().date()
        loan.save()
        book.available_copies += 1
        book.save()
        return Response({'status': 'Book returned successfully.'}, status=status.HTTP_200_OK)


class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer

    @action(detail=False, methods=['get'], url_path='top-active')
    def top_active(self, request):
        top_members = (
            Member.objects
            .filter(loans__is_returned=False)
            .annotate(active_loans=Count('loans', filter=models.Q(loans__is_returned=False)))
            .order_by('-active_loans')[:5]
        )

        data = []
        for member in top_members:
            data.append({
                'id': member.id,
                'username': member.user.username,
                'email': member.user.email,
                'active_loans': member.active_loans,
            })

        return Response(data, status=status.HTTP_200_OK)


class LoanViewSet(viewsets.ModelViewSet):
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer

    @action(detail=True, methods=['post'], url_path='extend_due_date')
    def extend_due_date(self, request, pk=None):
        loan = self.get_object()

        if loan.is_returned:
            return Response({'error': 'This loan has already been returned.'}, status=status.HTTP_400_BAD_REQUEST)

        if loan.due_date < timezone.now().date():
            return Response({'error': 'This loan is already overdue and cannot be extended.'}, status=status.HTTP_400_BAD_REQUEST)

        additional_days = request.data.get('additional_days')
        if not additional_days or not isinstance(additional_days, int) or additional_days <= 0:
            return Response({'error': 'additional_days must be a positive integer.'}, status=status.HTTP_400_BAD_REQUEST)

        loan.due_date += timedelta(days=additional_days)
        loan.save()

        serializer = LoanSerializer(loan)
        return Response(serializer.data, status=status.HTTP_200_OK)
